<template>
  <!-- Personenliste (UX3b, Entwurf A3): Tabelle ab 20 Personen, darunter
       Karten. Die GANZE Zeile ist klickbar (Prinzip K4) — sie führt auf das
       Profil. Kontaktwege (anrufen, schreiben) stehen in der Zeile und halten
       den Klick an, damit sie nicht im Profilsprung verschwinden.

       UX3b2 (Befunde 2, 3, 5): Die Fußzeile steht AUSSERHALB der Tabelle und
       immer unter dem Inhalt — vorher steckte sie im Tabellenkasten, der am
       Handy ausgeblendet ist, und verschwand mit ihm. Die Form der Liste
       kommt nach GESAMTZAHL (die Seite rechnet sie), nicht nach der Zahl der
       gerade sichtbaren Zeilen. -->
  <div class="dk-card pz-flaeche">
    <!-- Ladend (Prinzip I1/I5): der Platzhalter erscheint erst, wenn das
         Laden merklich dauert (useLadeSkelett), nicht bei jedem Wechsel. -->
    <DkSkelett v-if="laedtSkelett" form="tabelle" :anzahl="8" text="Personen werden geladen …" class="pz-zustand" />
    <!-- Fehler (Prinzip I5, Befund 6): gestalteter Zustand mit „Erneut
         versuchen“ — vorher stand hier eine nackte rote Zeile ohne Weg
         weiter. Der Knopf lädt die Liste erneut (Ereignis an die Seite). -->
    <DkEmpty
      v-else-if="fehler"
      icon="⚠"
      title="Die Liste ist nicht gekommen"
      :text="fehler"
      :erneut-versuchen="erneutLaden"
      class="pz-zustand"
    />

    <!-- Leer: zwei verschiedene Zustände (I5) — nichts gefunden (Suche) vs.
         noch keine Person. -->
    <DkEmpty
      v-else-if="!zeilen.length"
      icon="👥"
      :title="sucht ? 'Keine Person gefunden' : 'Noch keine Person'"
      :text="sucht
        ? 'Passe die Suche an oder lösche sie, um alle zu sehen.'
        : (darfAnlegen ? 'Lege die erste Person an.' : 'Sobald Personen erfasst sind, erscheinen sie hier.')"
    >
      <template v-if="!sucht && darfAnlegen" #aktion>
        <DkButton variant="primary" @click="$emit('anlegen')">
          Person anlegen
        </DkButton>
      </template>
    </DkEmpty>

    <!-- Tabelle (ab 20 Personen, Entwurf A3; Verwaltung mit eigenem Spaltensatz) -->
    <div v-else-if="form === 'tabelle'" class="pz-tabelle">
      <DkTable :spalten="spalten">
        <tr
          v-for="z in zeilen"
          :key="z.name"
          class="pz-zeile"
          :class="{ 'pz-zeile--ohne-profil': !hatProfil(z) }"
          :data-name="z.name"
        >
          <td class="pz-zelle-name">
            <a
              v-if="hatProfil(z)"
              class="pz-zeilenziel"
              :href="'#/mitglied/' + z.name"
              :aria-label="z.anzeigename + ' öffnen'"
            ><span class="pz-sr">Profil von {{ z.anzeigename }} öffnen</span></a>
            <span class="pz-person">
              <span class="dk-avatar pz-avatar" :style="avatarStil(z.anzeigename)">{{ initialen(z.anzeigename) }}</span>
              <span class="pz-name">{{ z.anzeigename || 'Ohne Namen' }}</span>
            </span>
          </td>
          <!-- UX3b2: Verwaltungsspalten (Status, Gruppen, persönliche Felder)
               nur, wo die Quelle sie wirklich hat — das Adressbuch liefert
               weder Status noch Gruppen, eine leere Spalte wäre eine Lüge. -->
          <td v-if="verwaltung" class="pz-zelle-status">
            <DkBadge :variant="statusVariante(z.status)">{{ statusWort(z.status) }}</DkBadge>
          </td>
          <td v-if="verwaltung" class="pz-zelle-gruppen">
            <span class="pz-gruppen">
              <DkBadge v-for="g in gruppenAnzeige(z)" :key="g" variant="neutral">{{ g }}</DkBadge>
              <span v-if="!gruppenAnzeige(z).length" class="pz-leer">–</span>
            </span>
          </td>
          <!-- Kontakt- und Ortsspalten (Review UI-R7b, Punkt 1 UND Punkt 3):
               Die Zellen standen ZWEIMAL im Markup (Verwaltung und
               Freigabe-Sicht) und ihre REIHENFOLGE war ein zweiter,
               handgepflegter Satz neben dem Kopf. Beides ist jetzt weg: die
               Zellen laufen über DIESELBE Spaltenliste wie der Kopf
               (`spalten`, aus `personenVerwaltung.mjs`), und jede Zelle steht
               im Quelltext GENAU EINMAL - ein `v-for` über die Schlüssel,
               ein `v-if` je Art.

               „Kontaktdaten nicht freigegeben“ deckt E-Mail UND Telefon mit
               `colspan="2"` ab; der Ort bekommt dann seine eigene Zelle, damit
               die Zeile ihre Zellenzahl behält. -->
          <template v-for="(key, i) in kontaktSpalten" :key="key">
            <!-- „Kontaktdaten nicht freigegeben“: EINE Zelle über E-Mail UND
                 Telefon (`colspan="2"`), damit die Zellenzahl zum Kopf passt.
                 Sie steht an der Stelle der ERSTEN der beiden Spalten; die
                 zweite entfällt — sonst hätte die Zeile eine Zelle zuviel. -->
            <td v-if="ohneKontaktdaten(z) && i === ersterKontaktIndex"
                colspan="2"
                class="pz-zelle-nicht-freigegeben"
            ><span class="pz-verborgen">{{ NICHT_FREIGEGEBEN }}</span></td>
            <template v-else-if="ohneKontaktdaten(z) && (key === 'email' || key === 'telefon')" />
            <!-- UI-R7c, Punkt 1: Telefon VOR E-Mail (Reihenfolge des Kopfes).
                 Beide Kontaktzellen schneiden ab (Stil unten), der volle Wert
                 steht als `title`. -->
            <td v-else-if="key === 'telefon'" class="pz-zelle-kontakt pz-zelle-telefon">
              <a
                v-if="z.telefonnummer"
                class="pz-kontakt"
                :href="'tel:' + telHref(z.telefonnummer)"
                :title="z.telefonnummer"
              >{{ z.telefonnummer }}</a>
              <!-- Leer: stiller Gedankenstrich. In der Verwaltung erbt die
                   Zelle den Zustand der E-Mail-Zelle („E-Mail verborgen“ steht
                   EINMAL je Zeile, sonst stünde der Satz zweimal nebeneinander). -->
              <span v-else :class="verwaltung ? emailErsatzKlasse(z) : 'pz-leer'">{{ telefonAnzeige(z.telefonnummer) }}</span>
            </td>
            <td v-else-if="key === 'email'" class="pz-zelle-kontakt pz-zelle-email">
              <a
                v-if="z.email"
                class="pz-kontakt"
                :href="'mailto:' + z.email"
                :title="z.email"
              >{{ z.email }}</a>
              <span v-else :class="emailErsatzKlasse(z)">{{ emailAnzeige(z.email, { angefordert: angefordert }).text }}</span>
            </td>
            <td v-else class="pz-zelle-ort" :title="z.ort || ''">{{ z.ort || '–' }}</td>
          </template>
          <td v-if="verwaltung" class="pz-zelle-adresse pz-mono">{{ adressZeile(z) }}</td>
          <td v-if="verwaltung" class="pz-zelle-geburtstag pz-mono">{{ z.geburtstag || '–' }}</td>
          <td v-if="verwaltung" class="pz-zelle-dabei pz-mono">{{ z.dabeiSeit || '–' }}</td>
          <!-- R-9 (Manuel 11.11.): „Daten anfragen“ — NUR wenn der Server die
               Zeile als anfragbar meldet (die Person hat nicht alles
               freigegeben) und noch keine Anfrage läuft/erging.

               Review UI-R7b, Punkt 3: Die Zelle hängt an DERSELBEN Bedingung
               wie ihre Überschrift (`fragenMoeglich`, s. `spalten` oben). Vorher
               stand der Kopf an `fragenMoeglich`, die Zelle aber an
               `!zeilenMenue` — in einer Liste ohne anfragbare Person hatte der
               Kopf vier Spalten und die Zeile fünf (eine leere Zelle zuviel).

               Review UI-R7b, Punkt 4: In der Handy-Lage (> 720 px, Handy quer)
               entfiel die Zelle ganz (`!zeilenMenue`) — die Tabelle stand dann
               mit leerer Aktionsspalte da, während das ⋯-Menü nur in den
               versteckten Karten lag: 0 sichtbare Knöpfe. Jetzt steht in der
               Tabelle IMMER eine Aktionszelle, wenn es die Spalte gibt; ihren
               Inhalt wählt die Lage (Knopf bzw. DkAktionen). -->
          <td v-if="!verwaltung && fragenMoeglich" class="pz-zelle-anfrage">
            <DkAktionen
              v-if="zeilenMenue && istAnfragbar(z)"
              :kennung="'person-anfrage-' + z.name"
              :label="'Aktionen für ' + z.anzeigename"
              :eintraege="anfrageEintraege(z)"
              @aktion="anfragen(z)"
            />
            <DkButton
              v-else-if="istAnfragbar(z)"
              class="pz-anfrage"
              variant="secondary"
              size="sm"
              :disabled="laeuft === z.name || istErgangen(z)"
              :aria-label="knopfLabel(z)"
              :title="istErgangen(z) ? 'Anfrage ist schon unterwegs' : ''"
              @click.stop="anfragen(z)"
            >{{ istErgangen(z) ? ANGEFRAGT_TEXT : KNOPF_TEXT }}</DkButton>
          </td>
        </tr>
      </DkTable>
    </div>

    <!-- Karten — dieselben Felder, gestapelt. Zwei Wege zu ihnen:
         · unter 20 Personen (Entwurf A3) zeigen sie die Vorschau,
         · am Handy ersetzen sie immer die Tabelle (deren min-width: 640px
           lief dort aus dem Bild).
         ACHTUNG: `v-show` statt `v-else` — die Karten müssen im DOM stehen,
         sonst kann CSS sie am Handy nicht einblenden; und `v-show` an einem
         `v-else` ist in Vue nicht erlaubt (Bedingungskette mit v-if). -->
    <ul v-show="form !== 'tabelle' || schmal" class="pz-karten">
      <li v-for="z in zeilen" :key="z.name" class="pz-karte" :data-name="z.name">
        <a
          v-if="hatProfil(z)"
          class="pz-zeilenziel"
          :href="'#/mitglied/' + z.name"
          :aria-label="z.anzeigename + ' öffnen'"
        ><span class="pz-sr">Profil von {{ z.anzeigename }} öffnen</span></a>
        <span class="dk-avatar pz-avatar" :style="avatarStil(z.anzeigename)">{{ initialen(z.anzeigename) }}</span>
        <span class="pz-karte-text">
          <span class="pz-name">{{ z.anzeigename || 'Ohne Namen' }}</span>
          <!-- R-9: Hat die Person nichts freigegeben, steht EINE Zeile statt
               einer Reihe von Gedankenstrichen — und daneben der Weg zur
               Anfrage. Die Datenfelder entfallen dann ganz. -->
          <template v-if="ohneKontaktdaten(z)">
            <span class="pz-karte-zeile">
              <span class="pz-verborgen">{{ NICHT_FREIGEGEBEN }}</span>
            </span>
          </template>
          <template v-else>
            <span class="pz-karte-zeile">
              <a v-if="z.email" class="pz-kontakt" :href="'mailto:' + z.email">{{ z.email }}</a>
              <span v-else :class="emailErsatzKlasse(z)">{{ emailAnzeige(z.email, { angefordert: angefordert }).text }}</span>
            </span>
            <span class="pz-karte-zeile">
              <a v-if="z.telefonnummer" class="pz-kontakt" :href="'tel:' + telHref(z.telefonnummer)">{{ z.telefonnummer }}</a>
              <span v-else :class="emailAnzeige(z.email, { angefordert: angefordert }).verborgen ? 'pz-verborgen' : 'pz-leer'">{{ telefonAnzeige(z.telefonnummer) }}</span>
              <span v-if="z.ort" class="pz-ort">{{ z.ort }}</span>
            </span>
          </template>
          <!-- UX3b2: Status und Gruppen auch in der Karte — auf dem Handy IST
               die Karte die Verwaltungszeile (dort gibt es keine Tabelle). -->
          <span v-if="verwaltung" class="pz-karte-zeile">
            <DkBadge v-if="!z.ohneStatus" :variant="statusVariante(z.status)">{{ statusWort(z.status) }}</DkBadge>
            <DkBadge v-for="g in gruppenAnzeige(z)" :key="g" variant="neutral">{{ g }}</DkBadge>
          </span>
        </span>
        <!-- R-9: „Daten anfragen“ steht in JEDER Darstellung, in der die Karten
             sichtbar sind (Review zu UI-R7, Punkt 2) — auch am Laptop unter 20
             Personen. In der Handy-Lage steht hier das Zeilenmenü „⋯“ statt des
             Knopfes (eine Aktion, ein Ort je Lage).

             Review UI-R7b, Punkt 5: Der Knopf hing nur an `!zeilenMenue` und
             war damit auch für NICHT anfragbare Zeilen da — gesperrt, mit dem
             falschen Tooltip („hat ihre Kontaktdaten freigegeben“ stand auch an
             der eigenen Zeile und an gelöschten Personen) und als sichtbarer,
             aber `aria-hidden`-Knopf. Jetzt hängt er wie in der Tabelle an
             `istAnfragbar(z)`: keine anfragbare Person, kein Knopf. -->
        <DkButton
          v-if="!zeilenMenue && istAnfragbar(z)"
          class="pz-anfrage pz-karte-anfrage"
          variant="secondary"
          size="sm"
          :disabled="laeuft === z.name || istErgangen(z)"
          :aria-label="knopfLabel(z)"
          :title="istErgangen(z) ? 'Anfrage ist schon unterwegs' : ''"
          @click.stop="anfragen(z)"
        >{{ istErgangen(z) ? ANGEFRAGT_TEXT : KNOPF_TEXT }}</DkButton>
        <!-- R-9: Am Handy kein Überfahren — die Anfrage steht deshalb im
             Zeilenmenü „⋯“ (DkAktionen), dieselbe Aktion wie der Knopf am
             Laptop. Nur in der Handy-Lage: am Laptop gehörte „⋯“ nicht in die
             Zeile (DEV-B6: nie die Handy-Bedienung am Schreibtisch). Den Knopf
             der Karte gibt es dann nicht (siehe oben) — das Menü ist der EINE
             Weg am Handy. -->
        <!-- Kein `class` an DkAktionen: die Komponente rendert Knopf +
             Teleport (Fragment) — ein Klassen-Attribut käme nirgends an
             (Vue-Warnung „Extraneous non-props attributes“). Die Lage regelt
             das CSS über den Auslöser selbst (`.pz-karte >
             .dk-ui-aktionen-ausloeser`). -->
        <DkAktionen
          v-if="zeilenMenue && istAnfragbar(z)"
          kennung="person-anfrage"
          :label="'Aktionen für ' + z.anzeigename"
          :eintraege="anfrageEintraege(z)"
          @aktion="anfragen(z)"
        />
        <DkSymbolChevron v-if="hatProfil(z)" class="pz-chevron" />
      </li>
    </ul>

    <!-- Fußzeile: Umfang + Blättern (Entwurf A3). Steht IMMER unter dem
         Inhalt — auch am Handy (dort ist die Tabelle ausgeblendet, die
         Fußzeile bleibt). Kennt die Quelle kein Blättern (Adressbuch), nennt
         sie nur die Anzahl: keine erfundene Seitenzahl, keine wirkungslosen
         Knöpfe. „Zurück“ ist auf Seite 1 deaktiviert — Zustand statt
         wirkungslosem Knopf. -->
    <div v-if="fuss" class="pz-fuss">
      <span class="pz-fuss-text">{{ fuss }}</span>
      <span v-if="knoepfe.sichtbar" class="pz-fuss-knoepfe">
        <DkButton
          variant="secondary"
          size="md"
          :disabled="!knoepfe.zurueck"
          @click="$emit('blaettern', seite - 1)"
        >Zurück</DkButton>
        <DkButton
          variant="secondary"
          size="md"
          :disabled="!knoepfe.weiter"
          @click="$emit('blaettern', seite + 1)"
        >Weiter</DkButton>
      </span>
    </div>
  </div>
</template>

<script setup>
/**
 * PersonenListe — die EINE Darstellung der Personenzeile (UX3b/UX3b2).
 *
 * Wird von „Personen → Liste“ (Admins, Quelle Mitgliederliste) und von
 * „Personen“ (alle anderen, Quelle Adressbuch) benutzt. Die Zeilenform kommt
 * fertig aus composables/personenZeilen.mjs; die Verwaltungsregeln (Spalten,
 * Fußzeile, Blätter-Zustand) aus composables/personenVerwaltung.mjs.
 *
 * Entscheidungen (Entwurf A3 + Review UX3b):
 *  • Tabelle ist Standard ab 20 Personen (GESAMTZAHL), sonst Karten. Am Handy
 *    ersetzen Karten die Tabelle immer.
 *  • Die ganze Zeile ist klickbar: ein ausgebreiteter Link (`.pz-zeilenziel`)
 *    deckt die Zelle ab; Kontaktwege (`mailto:`/`tel:`) liegen darüber und
 *    behalten ihren eigenen Klick.
 *  • „E-Mail verborgen“ steht EINMAL in der Zelle. Fordert die Verwaltung
 *    persönliche Daten NICHT an, sagt die Zeile das ehrlich („nicht
 *    angefordert“) statt dem Mitglied zu unterstellen, es verberge sie.
 *  • Gelöschte Person: kein Profil-Link (DSGVO-2d, `darfProfilLink`).
 *  • Blättern ist ein Ereignis an die Seite (die kennt die Quelle).
 * Nur Tokens, keine festen Farben.
 */
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkTable from '../ui/DkTable.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkBadge from '../ui/DkBadge.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import { useHandyLage } from '../../composables/handyLage.mjs'
import { telHref } from '../../composables/adressbuch.mjs'
import { darfProfilLink } from '../../composables/geloeschte-person.mjs'
import {
  emailAnzeige, telefonAnzeige, initialen,
} from '../../composables/personenZeilen.mjs'
import {
  ANGEFRAGT_TEXT, KNOPF_TEXT, NICHT_FREIGEGEBEN, istAnfragbar, ohneKontaktdaten,
} from '../../composables/datenAnfrage.mjs'
import {
  adressZeile, blaetterKnopfZustand, freigabeSpalten, fusszeileFuer,
  statusVariante, statusWort, verwaltungSpalten,
} from '../../composables/personenVerwaltung.mjs'

const props = defineProps({
  zeilen: { type: Array, default: () => [] },
  /** 'tabelle' | 'karten' — gerechnet von der Seite aus der GESAMTZAHL. */
  form: { type: String, default: 'karten' },
  laedt: { type: Boolean, default: false },
  fehler: { type: String, default: '' },
  sucht: { type: Boolean, default: false },
  gesamt: { type: Number, default: 0 },
  seite: { type: Number, default: 1 },
  seiten: { type: Number, default: 1 },
  darfAnlegen: { type: Boolean, default: false },
  /** Mitgliederadministrator: Status, Gruppen, persönliche Spalten. */
  verwaltung: { type: Boolean, default: false },
  /** Quelle der Zeilen ('liste' | 'adressbuch') — sie kennt Blättern oder nicht. */
  quelle: { type: String, default: 'liste' },
  /** Persönliche Daten sind angefordert (der Server liefert sie dann). */
  persoenlich: { type: Boolean, default: false },
})
const emit = defineEmits(['anlegen', 'blaettern', 'erneut', 'datenAnfrage'])

/** „Erneut versuchen“ im Fehlerzustand: die Seite kennt die Quelle und lädt. */
function erneutLaden() {
  emit('erneut')
}

/**
 * R-9: Die Zeile bittet um Freigabe. Der KNOPF bzw. das Zeilenmenü meldet nur
 * — die Anfrage selbst schickt die Seite (`mitglieder.daten_anfragen`), weil
 * nur sie die Antwort in eine Meldung übersetzen kann.
 *
 * `laeuft` hält den Doppelklick ab, SOLANGE die Anfrage unterwegs ist.
 * `ergangen` merkt sich die Person danach: der Knopf wird „Angefragt“ und
 * bleibt gesperrt (Review zu UI-R7, Punkt 3) — sonst schickte jeder weitere
 * Klick eine neue Anfrage an den Server. Gesperrt wird bei `gesendet: true`
 * UND bei `bereits: true`; „nicht zugestellt“ (`gesendet: false` ohne
 * `bereits`) gibt den Knopf frei, damit er dem Toast nicht widerspricht
 * (Review UI-R7b, Punkt 7).
 */
const laeuft = ref('')
const ergangen = ref(new Set())

/** Ist die Anfrage für diese Zeile schon unterwegs gewesen? */
function istErgangen(zeile) {
  return Boolean(zeile?.name) && ergangen.value.has(zeile.name)
}

/** Beschriftung/Vorlesetext des Knopfes — Zustand statt Vermutung. */
function knopfLabel(zeile) {
  const name = zeile?.anzeigename || 'die Person'
  return istErgangen(zeile) ? `${ANGEFRAGT_TEXT}: ${name}` : `${KNOPF_TEXT}: ${name}`
}

/** Der eine Menüeintrag des Zeilenmenüs (R-9) — dieselbe Beschriftung wie der
 *  Knopf am Laptop, kein zweiter Text. */
function anfrageEintraege(zeile) {
  return [{
    key: 'anfragen',
    label: istErgangen(zeile) ? ANGEFRAGT_TEXT : KNOPF_TEXT,
    icon: 'freigeben',
    disabled: laeuft.value === zeile?.name || istErgangen(zeile),
  }]
}

/**
 * `fertig(ok)` — die Seite meldet zurück, ob die Anfrage angekommen ist
 * (`true`/nichts = angenommen, auch „schon angefragt“; `false` = nicht
 * zugestellt). Nur `true` sperrt den Knopf (Punkt 7); bei „nicht zugestellt“
 * bleibt er bedienbar, passend zum Toast.
 */
function anfragen(zeile) {
  if (!zeile?.name || laeuft.value || istErgangen(zeile)) return
  laeuft.value = zeile.name
  emit('datenAnfrage', { name: zeile.name, anzeigename: zeile.anzeigename }, (ok = true) => {
    laeuft.value = ''
    if (ok !== false) ergangen.value = new Set([...ergangen.value, zeile.name])
  })
}

const { skelettSichtbar: laedtSkelett } = useLadeSkelett(computed(() => props.laedt))

// Schmale Anzeige (dieselbe Grenze wie das CSS unten: 720 px). Sie
// entscheidet NUR, ob die Karten SICHTBAR sind — die Daten sind dieselben.
const schmal = ref(false)
function breiteMessen() {
  if (typeof window === 'undefined') return
  schmal.value = window.innerWidth <= 720
}
/**
 * R-9: „Daten anfragen“ am Handy gehört ins Zeilenmenü „⋯“ — dort gibt es kein
 * Überfahren. Die Handy-Lage kommt aus der EINEN Regel (`useHandyLage`, also
 * Breite UND grober Zeiger), NICHT aus der Breite allein: ein schmal
 * gezogenes Laptop-Fenster bekäme sonst die Handy-Bedienung (DEV-B6/MT-1).
 */
const { istHandyLage } = useHandyLage()
/**
 * Zeilenmenü NUR in der Handy-Lage und dort statt des Knopfes in der Zeile.
 * Die Zeiger-ART wird nicht abgefragt (FIX-6c): außerhalb der Handy-Lage ist
 * „Daten anfragen“ dauerhaft sichtbar (Nacharbeit zu UI-R7b, Punkt 2).
 */
const zeilenMenue = computed(() => istHandyLage.value === true)

onMounted(() => {
  breiteMessen()
  window.addEventListener('resize', breiteMessen)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', breiteMessen)
})

/**
 * Hat der Server die persönlichen Felder liefern sollen? Nur die Verwaltung
 * mit eingeschaltetem Schalter — dann (und NUR dann) heißt eine leere
 * E-Mail-Zelle „E-Mail verborgen“. Vorher stand das bei ausgeschaltetem
 * Schalter in jeder Zeile und unterstellte dem Mitglied etwas.
 * Die Freigabe-Sicht (Adressbuch, Mitglieder) liefert IMMER, was freigegeben
 * ist — dort heißt eine leere E-Mail weiterhin „E-Mail verborgen“.
 */
const angefordert = computed(
  () => props.quelle !== 'liste' || (verwaltung.value && props.persoenlich === true),
)

/** Verwaltungs-Spaltensatz nur, wenn die Quelle Verwaltungsfelder hat. */
const verwaltung = computed(() => props.verwaltung === true && props.quelle === 'liste')

// Spaltensatz und Zellen müssen ZUSAMMENPASSEN: persönliche Spalten stehen
// darin, sobald die Verwaltung sie sehen darf — der Schalter ändert nur, ob
// der Server die WERTE liefert. Sonst stünde die E-Mail (die auch in den
// anderen Fällen nicht fehlen darf) unter einer falschen Überschrift.
//
// Review zu UI-R7, Punkt 1: BEIDE Sätze kommen aus `personenVerwaltung.mjs`
// (dieselbe Reihenfolge wie die Zellen im Markup). Eine eigene Liste hier im
// Baustein driftete vom Markup weg — 4 Überschriften, 5 Zellen.
const spalten = computed(() => (verwaltung.value
  ? verwaltungSpalten({ persoenlich: true })
  : freigabeSpalten({ anfrage: fragenMoeglich.value })))

/**
 * Die Kontakt-/Ortsspalten in der Reihenfolge des KOPFS
 * (Review UI-R7b, Punkt 1): Das Markup läuft über DIESE Liste statt über einen
 * zweiten, handgepflegten Zellensatz — eine Reihenfolge, eine Quelle.
 *
 * Die Zeile entscheidet je Datensatz, ob E-Mail und Telefon zu EINER Zelle
 * „Kontaktdaten nicht freigegeben“ (`colspan="2"`) verschmelzen; die
 * SPALTENFORM bleibt dieselbe.
 */
const kontaktSpalten = computed(() => spalten.value
  .filter((s) => ['email', 'telefon', 'ort'].includes(s.key))
  .map((s) => s.key))

/** Index der ersten Kontaktspalte — dort steht die verschmolzene Zelle. */
const ersterKontaktIndex = computed(() => kontaktSpalten.value
  .findIndex((k) => k === 'email' || k === 'telefon'))

/**
 * Gibt es in DIESER Liste überhaupt jemanden zu fragen? Nur dann hat die
 * Aktionsspalte eine Überschrift („Aktionen“) — eine Spalte, die nie einen
 * Knopf zeigt, wäre eine Behauptung.
 */
const fragenMoeglich = computed(() => props.zeilen.some((z) => istAnfragbar(z)))

/** Fußzeile nach Quelle: Adressbuch nennt nur die Anzahl (kein Blättern). */
const fuss = computed(() => fusszeileFuer({
  quelle: props.quelle,
  gesamt: props.gesamt,
  sichtbar: props.zeilen.length,
  seite: props.seite,
  seiten: props.seiten,
}))
const knoepfe = computed(() => blaetterKnopfZustand({
  quelle: props.quelle,
  seite: props.seite,
  seiten: props.seiten,
}))

/**
 * Ein Profil gibt es nur zu einer Kennung — und nicht für eine gelöschte
 * Person (DSGVO-2d, Befund 5). Vorher prüfte die Liste nur „Name vorhanden“;
 * `geloescht-…` bekam damit einen Link auf ein Profil, das es nicht gibt.
 */
function hatProfil(z) {
  return Boolean(z) && darfProfilLink(z)
}

/**
 * Wie eine leere Kontaktzelle aussieht:
 *  • „nicht angefordert“ → still: die Zelle zeigt „nicht angefordert“
 *    (Schalter aus, niemand hat etwas verborgen),
 *  • „E-Mail verborgen“ → gedämpft/kursiv,
 *  • leerer Wert → stiller Gedankenstrich.
 */
function emailErsatzKlasse(z) {
  const anzeige = emailAnzeige(z?.email, { angefordert: angefordert.value })
  if (anzeige.angefordert === false) return 'pz-leer'
  if (anzeige.verborgen) return 'pz-verborgen'
  return 'pz-leer'
}

/** Gruppen einer Zeile, kurz gehalten (erste zwei + „+n“). */
function gruppenAnzeige(z) {
  const alle = Array.isArray(z?.gruppen) ? z.gruppen : []
  if (alle.length <= 2) return alle
  return [...alle.slice(0, 2), `+${alle.length - 2}`]
}

// Farbpaare des Avatars: dieselben Tokens wie die Mitgliederliste (keine
// neuen Farbwerte). Nur der Hintergrund streut, die Schrift bleibt Textfarbe.
const AVATAR_PAARE = [
  'var(--dk-avatar-1-bg)', 'var(--dk-avatar-2-bg)', 'var(--dk-avatar-3-bg)',
  'var(--dk-avatar-4-bg)', 'var(--dk-avatar-5-bg)', 'var(--dk-avatar-6-bg)',
]
/** Symbol „Weiter“ (Chevron) — auf der Textlinie, Strich in Schriftstärke. */
const DkSymbolChevron = h('svg', {
  width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
  'aria-hidden': 'true',
}, [h('polyline', { points: '9 18 15 12 9 6' })])
function avatarStil(name) {
  const n = String(name || 'A').trim()
  const summe = (n.charCodeAt(0) || 65) + (n.length > 1 ? n.charCodeAt(n.length - 1) : 0)
  return { background: AVATAR_PAARE[summe % AVATAR_PAARE.length] }
}

defineExpose({ telHref })
</script>

<style scoped>
.pz-flaeche { padding: 0; overflow: hidden; }
.pz-zustand { padding: var(--sp-5) var(--pad); }

/* Spaltenbreiten: Name breit, Kontaktwege mittel, Ort knapp. */
.pz-zelle-name { width: 28%; }
.pz-zelle-kontakt { width: 18%; }
.pz-zelle-ort { width: 18%; color: var(--muted); }
/* Verwaltungsspalten: die persönlichen bleiben schmal und still (sie sind
   Beifang, die Handlung ist die Zeile selbst). */
.pz-zelle-status, .pz-zelle-gruppen, .pz-zelle-adresse,
.pz-zelle-geburtstag, .pz-zelle-dabei { color: var(--muted); }
.pz-gruppen { display: inline-flex; flex-wrap: wrap; gap: var(--sp-1); align-items: center; }
/* Tabellenzahlen in gleicher Breite (Prinzip Ä3, Token --fs-tabular). */
.pz-mono { font-variant-numeric: var(--fs-tabular); }

/* Ausgebreiteter Zeilen-Link: liegt über der GANZEN Zeile, damit jeder Punkt
   der Zeile das Profil öffnet (Prinzip K4) — Kontaktwege über ihm bleiben
   klickbar (.pz-kontakt, position: relative). */
.pz-zeile { cursor: pointer; }
/* Die ZELLEN tragen den relativen Bezug: `position: relative` an einem <tr>
   wird im Tabellensatz ignoriert (der Link bekam Breite 0 und die Zeile war
   trotzdem nicht klickbar — im Browser gemessen). */
.dk-ui-table tbody tr.pz-zeile > td { position: relative; }
.pz-karte { position: relative; }
/* Zwei Klassen: `a { position: relative }` aus index.css ist eine
   ELEMENT-Regel und schlägt eine einteilige Klassen-Regel gleicher Stufe —
   gemessen im Browser (Link blieb `relative`, Breite 0). */
.pz-zeilenziel.pz-zeilenziel {
  position: absolute;
  inset: 0;
  z-index: 0;
  border-radius: inherit;
  text-decoration: none;
}
.pz-zeilenziel.pz-zeilenziel:focus-visible {
  /* Rahmenbreite aus der Skala: 4 px = --sp-1 (Wächter UX1a lässt keine
     festen Werte zu); optisch innen, damit die Zeile nicht wächst. */
  outline: var(--sp-1) solid var(--focus-ring);
  outline-offset: calc(var(--sp-1) * -1);
}
.pz-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: calc(var(--sp-1) * -0.25);
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

.pz-person { display: flex; align-items: center; gap: var(--sp-3); min-width: 0; }
.dk-avatar.pz-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  /* Avatar 32 px = --sp-6 (Skala), nicht als fester Wert (Wächter UX1a). */
  width: var(--sp-6);
  height: var(--sp-6);
  border-radius: 50%;
  font-size: var(--fs-sm);
  font-weight: var(--fw-fett);
  color: var(--text);
}
.pz-name {
  font-weight: var(--fw-mittel);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Kontaktwege liegen ÜBER dem Zeilen-Link (eigener Klick gewinnt). */
.pz-kontakt {
  position: relative;
  z-index: 1;
  color: var(--muted);
  text-decoration: none;
}
.pz-kontakt:hover { color: var(--text); text-decoration: underline; }
.pz-kontakt:focus-visible {
  outline: var(--sp-1) solid var(--focus-ring);
  outline-offset: var(--sp-1);
  border-radius: var(--radius-sm);
}
/* UI-R7c, Punkt 1: KEIN Überlauf in die Nachbarspalte.
   Mit Aktionsspalte steht die Tabelle auf `table-layout: fixed` (DkTable
   `.has-aktion`) — dann bestimmt die Spaltenbreite die Zelle, nicht der
   Inhalt. Eine lange Adresse schob sich trotzdem in die Telefon-Spalte
   („rebekka@example.org07071 2345“), weil weder Zelle noch Link abschnitten.
   Die Zelle schneidet ab, der Wert bekommt eine Ellipse; den vollen Wert
   trägt `:title`. Gleiches gilt für Telefon; der Ort ist ein blanker Textknoten
   in der Zelle und wird von deren `overflow` beschnitten. */
.pz-zelle-kontakt { overflow: hidden; }
.pz-zelle-kontakt .pz-kontakt {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pz-zelle-ort { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* „E-Mail verborgen“ ist Zustand, keine Aktion — gedämpft, nie ein Link. */
.pz-verborgen { color: var(--subtle); font-style: italic; }
/* Leerer Wert (nicht freigegeben/nicht hinterlegt): stiller Gedankenstrich. */
.pz-leer { color: var(--subtle); }
/* Verwaltung, Schalter aus: die Zeile sagt es selbst („Persönliche Daten
   nicht angefordert“) — normal getönt, kein Vorwurf an das Mitglied. */
.pz-nicht-angefordert { color: var(--muted); }

/* ── R-9: „Daten anfragen“ ─────────────────────────────────────────────────
   Der Knopf steht in einer eigenen Zelle (bzw. in der Karte) und ist
   DAUERHAFT sichtbar — kein Überfahren nötig: ein Knopf, den man erst
   überfahren muss, gäbe es am Tablet nicht, und die Zeigerart darf nirgends
   abgefragt werden (FIX-6c). Die Handy-Lage zeigt hier das Zeilenmenü „⋯“. */
.pz-zelle-anfrage { width: 1%; white-space: nowrap; text-align: right; }
/* „Angefragt“ ist ZUSTAND, keine Aufforderung: der Knopf bleibt sichtbar und
   antippbar, gesperrt wird er über `disabled` (nicht über `pointer-events`). */
.pz-anfrage:disabled { opacity: 1; }

/* Kontaktzelle ohne Freigabe: EIN Satz über beide Spalten (colspan=2 trägt
   die Breite, hier nur die Tönung). */
.pz-zelle-nicht-freigegeben { color: var(--subtle); }

/* Zeilenmenü am Handy (R-9): der „⋯“-Knopf sitzt auf der Zeile wie der
   Chevron; das Menü selbst liegt im Teleport (DkAktionen). */
.pz-karte > .dk-ui-aktionen-ausloeser { flex: 0 0 auto; }
/* Anfrage-Knopf der KARTE (Review zu UI-R7, Punkt 2): Grundform für Karten mit
   Anfrage — dauerhaft sichtbar, nie überfahren. */
.pz-karte-anfrage { flex: 0 0 auto; white-space: nowrap; align-self: center; }

.pz-tabelle :deep(tbody tr.pz-zeile:hover td) { background: var(--surface-hover); }

.pz-fuss {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--gap);
  flex-wrap: wrap;
  padding: var(--sp-3) var(--pad);
  /* 1-px-Trenner als Schatten statt `border` — kein fester Längenwert im
     Stil (Wächter UX1a), gleiche Optik wie die Tabellenlinien. */
  box-shadow: inset 0 1px 0 var(--line);
}
.pz-fuss-text { font-size: var(--fs-sm); color: var(--muted); font-variant-numeric: var(--fs-tabular); }
.pz-fuss-knoepfe { display: flex; gap: var(--sp-2); }

/* Karten (unter 20 Personen): je Person eine Zeile, Trennlinie nur zwischen
   Zeilen (Prinzip Ä2: Abstand statt Rahmen). */
.pz-karten { list-style: none; margin: 0; padding: 0; }
.pz-karte {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--pad);
  min-height: var(--row-h);
  box-shadow: inset 0 1px 0 var(--line);
}
.pz-karte:first-child { box-shadow: none; }
.pz-karte:hover { background: var(--surface-hover); }
.pz-karte-text { display: flex; flex-direction: column; gap: var(--sp-1); min-width: 0; flex: 1; }
.pz-karte-zeile { display: flex; gap: var(--sp-3); flex-wrap: wrap; font-size: var(--fs-sm); align-items: center; }
.pz-ort { color: var(--subtle); }
.pz-chevron { flex: 0 0 auto; color: var(--subtle); align-self: center; }

/* Handy: Karten statt Tabelle. Die Tabelle hat `min-width: 640px` (DkTable,
   damit Spalten scrollen statt zu quetschen) — am Handy lief die E-Mail-Spalte
   dadurch aus dem Bild (im Screenshot gesehen). Der Personen-Baustein zeigt
   dort bereits Karten, deshalb wird die Tabelle ausgeblendet statt gescrollt.
   UX3b2 (Befund 3): Ausgeblendet wird NUR die Tabelle — die Fußzeile steht
   außerhalb und bleibt stehen (vorher steckte sie mit im Kasten und war am
   Handy weg). */
@media (max-width: 720px) {
  .pz-tabelle { display: none; }
  .pz-karten { display: block; }
  .pz-zelle-name, .pz-zelle-kontakt, .pz-zelle-ort { width: auto; }
  /* Trefferfläche ≥ 44 px am groben Zeiger (Konzept; --control-h wird im
     @media (pointer: coarse)-Block auf 44 px gesetzt). */
  .pz-karte { min-height: var(--control-h); padding: var(--sp-3) var(--sp-4); }
  .pz-fuss { padding: var(--sp-3) var(--sp-4); }
}
</style>
