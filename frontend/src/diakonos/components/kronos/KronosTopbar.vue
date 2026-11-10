<template>
  <div class="kronos-kopf">
    <header class="kronos-header">
      <div class="header-left">
        <!-- UX3i (Entwurf A4): EINE Kopfzeile.
             Links: die Reiter (Monat · Woche · Liste · Zu prüfen (n)); am Handy
             davor unverändert der Umschalter der Kalenderliste.
             Rechts: „Kalender“ (Auswahl, mit Zähler) · „Heute“ · ‹ › ·
             der EINE Primärknopf „+ Termin anlegen“ · ein „⋯“-Menü für
             Ressourcenplan / Verwalten / Importieren / Hilfe.
             Das Auswahlfeld „Monat“ ist entfallen — die Reiter bestimmen die
             Ansicht (vorher gab es sie zweimal). -->
        <template v-if="!pruefTafel">
          <!-- UXK-R9: Am Handy liegt die Kalenderliste (Kalenderliste,
               CalDAV-Anleitung, Import) ausserhalb des Bildes. Dieser Knopf
               oeffnet sie — nur auf schmalen Bildschirmen sichtbar.
               DEV-B6 (Review-Nacharbeit 10.11.): KEIN zweiter
               Navigationseinstieg neben dem Menü-Knopf der App-Kopfzeile.
               In der Handy-Lage sitzt oben links bereits der Menü-Knopf
               (Schublade mit der gesamten Navigation); die Kalenderliste
               erreicht man über den Kalender-Knopf rechts. Der Umschalter
               bleibt nur als Rückfall ohne Menü-Knopf verfügbar und ist
               deshalb nicht mehr eingeblendet. Der Block bleibt im Markup,
               weil A10/A4 ihn über `$emit('sidebarToggle')` kennt und die
               Kalenderliste weiterhin einen Auslöser braucht, wenn die
               Schublade fehlt (Vollbild der Prüf-Tafel). -->
          <DkButton
            v-if="zeigeListenUmschalter"
            class="sidebar-toggle-btn"
            variant="secondary"
            aria-label="Meine Kalender und Hilfe anzeigen"
            title="Meine Kalender"
            @click="$emit('sidebarToggle')"
          >
            <template #icon>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>
            </template>
          </DkButton>
        </template>
        <!-- Die Reiterleiste steht LINKS in der Kopfzeile (A4). Sie kommt aus
             `menue.kalenderReiter` — eine Quelle für Beschriftung,
             Reihenfolge und „nur für Moderatoren“. Gerendert wird IMMER
             (ein v-if an der Komponente ließ sie nach dem Wechsel auf
             „Zu prüfen“ gar nicht erst entstehen, im Wegwerf-Stack gemessen).

             DEV-B2 (Befund DMB-8e166c0aacff): Auf der Prüf-Tafel ist die
             Leiste IDENTISCH zum Kalender — „Monat · Woche · Liste“ sind dort
             LINKS zurück in den Kalender (`#/kalender?ansicht=…`, ausgewertet
             von `pages/Kalender.vue`), keine toten Schaltflächen. Vorher
             filterte diese Komponente sie weg; Moderation.vue verspricht seit
             UX3d das Gegenteil. -->
        <KalenderReiter
          class="kronos-reiter"
          :class="{ 'kronos-reiter--tafel': pruefTafel }"
          :options="reiter"
          :model-value="gewaehlterReiter"
          @waehlen="onReiterWaehlen"
        />
      </div>

      <div v-if="!pruefTafel" class="header-right">
        <!-- A4: Kalenderauswahl als Popover, Zähler der eingeblendeten. -->
        <DkButton
          class="kalender-auswahl-btn"
          data-kalender-ausloeser="1" data-kalender-sichtbar="1"
          variant="secondary"
          :aria-expanded="auswahlOffen ? 'true' : 'false'"
          aria-haspopup="dialog"
          aria-label="Kalender auswählen"
          title="Meine Kalender ein-/ausblenden"
          @click="$emit('kalenderAuswahlUmschalten')"
        >
          <template #icon><DkSymbol name="kalender" :groesse="16" /></template>
          <span class="kalender-auswahl-label">Kalender</span>
          <span v-if="eingeblendet !== null" class="kalender-auswahl-zahl" aria-hidden="true">{{ eingeblendet }}</span>
        </DkButton>

        <!-- „Heute“: am Desktop mit Beschriftung. Am Handy ist die Beschriftung
             ausgeblendet — dort zeichnet die Schaltfläche bisher NICHTS (leerer
             Knopf, Review 07.11.). Jetzt steht dort das Kalender-Symbol; der
             Name bleibt als aria-label und Tooltip. -->
        <DkButton class="todaybutton" variant="secondary" aria-label="Zum heutigen Tag springen" title="Heute" @click="$emit('today')">
          <template #icon><DkSymbol name="kalender" class="today-symbol" :groesse="16" /></template>
          <span class="today-label">Heute</span>
        </DkButton>

        <DkButton class="nav-btn prev-month" variant="secondary" aria-label="Vorheriger Zeitraum" title="Zurück" @click="$emit('prev')">
          <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M15 6l-6 6 6 6"/></svg>
          </template>
        </DkButton>
        <DkButton class="nav-btn next-month" variant="secondary" aria-label="Nächster Zeitraum" title="Weiter" @click="$emit('next')">
          <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M9 6l6 6-6 6"/></svg>
          </template>
        </DkButton>

        <!-- Der EINE Primärknopf je Ansicht (Regel UX1h / A4). Ohne
             Schreibrecht gibt es ihn nicht (UXK-R10) — dann steht der ruhige
             Hinweis „Nur lesen“ statt eines toten Knopfes. -->
        <DkButton
          v-if="canWrite"
          class="termin-anlegen-btn"
          variant="primary"
          data-primaer="1"
          aria-label="Termin anlegen"
          @click="$emit('terminAnlegen')"
        >
          <template #icon>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
          </template>
          Termin anlegen
        </DkButton>
        <span v-else class="readonly-hinweis" title="Du kannst Termine nur lesen">
          <DkSymbol name="ansehen" :groesse="16" />
          <span class="readonly-label">Nur lesen</span>
        </span>

        <!-- A4: alles Seltene in EIN Menü — „Ressourcenplan“, „Kalender
             verwalten“, „Kalender importieren“, „Hilfe & Infos“. System-
             symbole aus dem Vorrat, keine Emoji. -->
        <DkAktionen
          kennung="kalender-kopf"
          :eintraege="menue"
          label="Weitere Kalender-Aktionen"
          menue-label="Weitere Kalender-Aktionen"
          @aktion="onMenueAktion"
        />
      </div>
    </header>
  </div>
</template>

<script setup>
/**
 * KronosTopbar — die Kopfzeile des Kalenders (Entwurf A4, UX3i).
 *
 * Aufbau: EINE Zeile. Links die Reiter, rechts die Werkzeuge in der
 * Reihenfolge „Kalender · Heute · ‹ › · + Termin anlegen · ⋯“. Zwei frühere
 * Bedienelemente sind ENTFALLEN:
 *
 *   * das Auswahlfeld „Monat“ — die Reiter bestimmen die Ansicht, das Feld
 *     war ein zweiter Weg zu demselben Zustand;
 *   * der Umschalter Ansehen/Bearbeiten — Begründung im Kartenkommentar von
 *     UX3i: Bearbeiten ist über den Klick auf einen Termin und über
 *     „Termin anlegen“ erreichbar; Ziehen/Ändern im Raster ist bei
 *     bestehendem Schreibrecht immer möglich (die Seite schaltet es frei),
 *     und der gefüllte Umschalter war ein zweiter Hauptknopf neben
 *     „Termin anlegen“ (Regel: genau ein Primärknopf je Ansicht).
 *
 * Rechte und Kennzahlen kommen von der Seite; hier wird nichts entschieden.
 */
import { computed } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import KalenderReiter from './KalenderReiter.vue'
// UX3d/UX3i: Reiterleiste und Sichtbarkeitsregel „nur Moderatoren“ aus EINER
// Quelle (dieselbe Liste prüfen die Wächter-Tests ux3d und ux3i).
import { kalenderReiter } from '../../menue.js'
import { kalenderMenue } from './kalenderRechte.mjs'

const props = defineProps({
  /** Monatstitel der Seite (in A4 steht er im Kartenkopf, nicht hier). */
  dateTitle: { type: String, default: '' },
  currentView: { type: String, default: 'dayGridMonth' },
  /** UXK-R10: mindestens ein Kalender mit Schreibrecht. */
  canWrite: { type: Boolean, default: true },
  /** UX3d: Reiter „Zu prüfen“ zeigen (Moderator mindestens eines Kalenders). */
  canModerate: { type: Boolean, default: false },
  /** Zahl offener Prüfungen — `null` = unbekannt (dann ohne Zahl). */
  offeneZahl: { type: Number, default: null },
  /** Zahl der eingeblendeten Kalender (Zähler am Knopf „Kalender“). */
  eingeblendet: { type: Number, default: null },
  /** Kalenderauswahl (Popover) ist offen. */
  auswahlOffen: { type: Boolean, default: false },
  /**
   * Darf die Person Kalender verwalten/importieren? Die Seite entscheidet das
   * aus `get_current_user_context` (Administrator ODER Kalenderadministrator)
   * — die Kopfzeile prüft keine Rollen selbst (eine Quelle, siehe
   * `kalenderRechte.mjs`).
   */
  istKalenderAdmin: { type: Boolean, default: false },
  /**
   * Lesemodus (`true`, Standard wie vor UX3i) oder Bearbeiten. Der Umschalter
   * steht dezent im „⋯“-Menü; gefüllte Knöpfe bleiben der Hauptaktion
   * vorbehalten (Regel UX1h).
   */
  lesemodus: { type: Boolean, default: true },
  /**
   * Die Kopfzeile gehört zur Prüf-Tafel. Die Reiterleiste ist dort DIESELBE
   * wie im Kalender — „Monat · Woche · Liste“ führen als Links zurück
   * (`#/kalender?ansicht=…`), „Zu prüfen“ ist als aktuelle Seite markiert.
   * Die Werkzeuge der Kalender-Ansicht (Heute, ‹ ›, „Termin anlegen“, „⋯“)
   * stehen auf der Tafel nicht — dort gilt die Aktionszeile der Tafel
   * (genau ein Primärknopf, S1).
   */
  pruefTafel: { type: Boolean, default: false },
  /** Aktiver Reiter: `kalender`, `pruefen` oder eine Kalender-Ansicht. */
  aktiverReiter: { type: String, default: 'kalender' },
  /**
   * DEV-B6 (Review-Nacharbeit 10.11.): Listen-Umschalter der Kalenderliste
   * zeigen? Die App-Kopfzeile trägt in der Handy-Lage bereits den Menü-Knopf
   * (Schublade) — ein zweiter Navigationseinstieg daneben war der Befund.
   * Die Seite schaltet ihn deshalb standardmäßig AUS und nur dort ein, wo
   * es keinen Menü-Knopf gibt. Der Emit `sidebarToggle` bleibt bestehen.
   */
  listenUmschalter: { type: Boolean, default: false },
})
const zeigeListenUmschalter = computed(() => props.listenUmschalter === true)

const emit = defineEmits([
  'prev', 'next', 'today', 'viewChange', 'resourceToggle',
  'sidebarToggle', 'kalenderAuswahlUmschalten', 'terminAnlegen', 'hilfe',
  // Nacharbeit 07.11.: Lesemodus umschalten und die eigenen abgelehnten
  // Termine öffnen (beides aus dem „⋯“-Menü).
  'lesemodusWechsel', 'abgelehnteTermine',
])

const RESOURCE_VIEW_MAP = {
  dayGridMonth: 'resourceTimelineMonth',
  timeGridWeek: 'resourceTimelineWeek',
  timeGridDay:  'resourceTimelineDay',
  listMonth:    'resourceTimelineWeek',
}
const RESOURCE_VIEWS = new Set(Object.values(RESOURCE_VIEW_MAP))

const lastNormalView = computed(() => {
  const v = props.currentView
  return RESOURCE_VIEWS.has(v) ? 'dayGridMonth' : v
})

// UX3d: Reiterleiste — welche Einträge erscheinen, entscheidet
// `menue.kalenderReiter`. Die Zahl bleibt `null`, solange sie unbekannt ist
// (kein erfundenes „0“).
//
// DEV-B2: Auf der Prüf-Tafel ist die Leiste IDENTISCH zum Kalender. Die drei
// Ansichten sind dort LINKS zurück in den Kalender (`#/kalender?ansicht=…`),
// keine Umschalter dieser Seite — deshalb bekommen sie auf der Tafel ein
// eigenes Ziel (`tafelZiel`), und `KalenderReiter` zeichnet sie als `<a>`.
const reiter = computed(() => {
  const liste = kalenderReiter({
    can_moderate: props.canModerate === true,
    offeneZahl: props.offeneZahl,
  })
  if (!props.pruefTafel) return liste
  return liste.map(r => (r.ansicht === true
    ? { ...r, ansicht: false, href: tafelZiel(r) }
    : r))
})

/**
 * Ziel eines Ansichts-Reiters auf der Prüf-Tafel: zurück in den Kalender, mit
 * der gewünschten Ansicht im Abfrageteil. Die Adresse ist lesbar und
 * teilbar (Prinzip N4/„wiedererkennen statt erinnern“) — `pages/Kalender.vue`
 * wertet `ansicht=monat|woche|liste` beim Öffnen aus.
 */
function tafelZiel(r) {
  const werte = new URLSearchParams({ ansicht: String(r.id) })
  return `#/kalender?${werte.toString()}`
}

// Welcher Eintrag ist aktiv? „Zu prüfen“ ist eine EIGENE Seite; im Kalender
// entscheidet die Ansicht. Ressourcenansichten (Timeline) gehören zur
// Ansicht, aus der sie geöffnet wurden — das ist `lastNormalView`.
const gewaehlterReiter = computed(() => {
  if (props.aktiverReiter === 'pruefen') return 'pruefen'
  const sicht = lastNormalView.value
  if (sicht === 'timeGridWeek') return 'woche'
  if (sicht === 'timeGridDay') return 'tag'
  if (sicht === 'listMonth') return 'liste'
  return 'monat'
})

/**
 * Klick auf einen Reiter: „Zu prüfen“ ist ein Link (navigiert der Browser).
 * Ansichten derselben Seite wechselt diese Komponente über denselben Weg wie
 * das frühere Auswahlfeld (`viewChange`), damit Kalender und Kopfzeile eine
 * Wahrheit behalten.
 */
function onReiterWaehlen(r) {
  if (!r || r.ansicht !== true) return
  emit('viewChange', r.aktiv)
}

// A4: das „⋯“-Menü. Symbolnamen kommen aus dem Vorrat (`symbole.mjs`).
// Nacharbeit 07.11.: Welche Einträge erscheinen, entscheidet EINE Funktion
// (`kalenderRechte.kalenderMenue`) — Verwalten/Import nur mit der Rolle
// „Administrator“ ODER „Kalenderadministrator“ (wie bisher in der
// Kalenderliste), „Bearbeiten“ nur mit Schreibrecht, „Abgelehnte Termine“ für
// alle (die Daten liefert der Server, er liefert nur die eigenen).
const menue = computed(() => kalenderMenue({
  istKalenderAdmin: props.istKalenderAdmin === true,
  hatSchreibrecht: props.canWrite === true,
  lesemodus: props.lesemodus !== false,
}))

/** DkAktionen meldet `{ eintrag, index }` — hier wird nur das Ereignis gebraucht. */
function onMenueAktion(ereignis) {
  const eintrag = ereignis && ereignis.eintrag ? ereignis.eintrag : ereignis
  if (!eintrag) return
  if (eintrag.key === 'ressourcenplan') {
    emit('resourceToggle')
  } else if (eintrag.key === 'hilfe') {
    emit('hilfe')
  } else if (eintrag.key === 'bearbeiten') {
    // Der Eintrag heißt nach der HANDLUNG, die er ermöglicht: im Lesemodus
    // schaltet er das Bearbeiten ein und umgekehrt.
    emit('lesemodusWechsel', props.lesemodus === true)
  } else if (eintrag.key === 'abgelehnte') {
    emit('abgelehnteTermine')
  }
  // „Kalender verwalten“ / „Kalender importieren“ sind echte Links
  // (`href` in `kalenderRechte.mjs`) — der Browser navigiert.
}
</script>

<style scoped>
/* Kopf + Reiter als EIN Block. Die frühere Trennlinie unter der Leiste fällt
   weg (A4: die Karte trennt sich über Fläche und Schatten, nicht über eine
   Linie — Prinzip Ä2). */
.kronos-kopf {
  flex: 0 0 auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
}
.kronos-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  /* UX3d: `min-height` allein ließ die Kopfzeile am Handy auf der festen
     Zeilenhöhe stehen, während sie ZWEI Zeilen umbrach (`flex-wrap`) — die
     zweite Zeile ragte aus dem Kasten und legte sich über die Reiterleiste
     darunter. `height: auto` lässt den Kasten mitwachsen. */
  height: auto;
  min-height: var(--control-h);
  padding: var(--sp-2) 0;
  gap: var(--sp-4);
  /* UXK-008: Auf schmalen Bildschirmen darf die Kopfzeile nicht aus dem
     Fenster laufen — die Umbruchfähigkeit ist die Grundlage dafür, dass die
     Werkzeuge am Handy erreichbar bleiben. */
  flex-wrap: wrap;
}
.header-left,
.header-right {
  display: flex;
  align-items: center;
  /* Innerhalb einer Gruppe gehört zusammen (Prinzip S3): 8 px. */
  gap: var(--sp-2);
  /* min-width:0 erlaubt es den Flexkindern zu schrumpfen statt die Zeile zu
     sprengen (Vorbedingung fuer den Umbruch). */
  min-width: 0;
}
.header-right { margin-left: auto; }

/* Die Reiterleiste sitzt im Kopf und trägt dort KEINE eigene Unterlinie
   (A4: Reiter + Werkzeuge stehen auf einer Linie). */
.kronos-reiter { margin: 0; border-bottom: 0; padding: 0; }
.kronos-reiter--tafel { margin: 0; }

/* A4: „Kalender“ trägt einen Zähler; er steht als ruhige Zahl neben dem
   Namen, nicht als Abzeichen mit eigener Fläche. */
.kalender-auswahl-zahl {
  min-width: var(--sp-4);
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.kalender-auswahl-btn[aria-expanded="true"] {
  background: var(--surface-hover);
  border-color: var(--line-strong);
}

/* Symbolknöpfe ‹ › : quadratisch, Klickfläche --control-h (bei
   Fingerbedienung 44 px, siehe unten). */
.nav-btn { width: var(--control-h); padding: 0; }
/* UXK-R9: Der Umschalter für die Kalender-Seitenleiste wird nur am Handy
   gebraucht; am Desktop ist die Leiste ohnehin sichtbar. */
.sidebar-toggle-btn { display: none; }
.readonly-hinweis {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  height: var(--filter-h);
  padding: 0 var(--sp-3);
  font-size: var(--fs);
  color: var(--muted);
}

/* ── Handy (≤ 720 px): die bisherige Anordnung bleibt ─────────────────────
   UX3i ändert nur den Desktop; A10 (Mobil-Kalender) ist eine eigene Karte.
   Reihenfolge und Erreichbarkeit bleiben erhalten, nichts wird kleiner als
   44 px (K4).
   DEV-B6 (Manuel 09.11.): Beschriftungen werden weggelassen, Symbole ersetzt
   — das ist die platzsparende LEISTEN-Lage (schmales Touchgerät bzw. flaches
   Querformat), nicht bloß ein schmales Fenster. Ein Maus-Laptop bei 702 px
   behält die vollständige Kopfzeile; seine Werkzeuge brechen bei 1100 px in
   eine zweite Zeile.
   DEV-B6 (Review-Nacharbeit 10.11.): Die Lage ist die KLASSE
   `.dk-app--handy` (Quelle `composables/handyLage.mjs`) — kein eigener
   Media-String mehr (Review-Punkt 5: „KronosTopbar-Block hängt noch an
   nacktem max-width: 720“). Die Wähler stehen OHNE `:global` — der
   Scope-Anhang landet am letzten Selektor, und der liegt im eigenen
   Template. */
.dk-app--handy .kronos-header .header-right {
  order: 3;
  /* `0 0 100%` hält die Zeile am Fenster (siehe UX3d: `1 0 100%` wuchs mit
     dem Inhalt und ragte über den Kopf hinaus) — nur in der Leisten-Lage,
     ohne untere Leiste bliebe der Kopf sonst unnötig zweizeilig.
     UX3i (Review): KEIN `margin-left: auto` in dieser Zeile — der
     automatische Rand verbraucht am Handy die ganze freie Breite und die
     Werkzeuge rutschten aus dem Bild (gemessen 390 px: „Termin anlegen“
     und „⋯“ hinter dem Rand). Am Desktop bleibt er (siehe oben). */
  flex: 0 0 100%;
  margin-left: 0;
  min-width: 0;
  justify-content: flex-end;
  flex-wrap: wrap;
  row-gap: var(--sp-2);
}
/* Am Handy hat die Reiterleiste ihre eigene Zeile: sie soll volle Breite
   bekommen und nicht neben dem Menü-Knopf umbrechen. */
.dk-app--handy .kronos-header .header-left { flex-wrap: wrap; }
.dk-app--handy .kronos-header .today-label { display: none; }
.dk-app--handy .kronos-header .todaybutton { width: var(--control-h); padding: 0; }
/* Ohne Beschriftung muss das Symbol stehen — sonst wäre der Knopf leer. */
.dk-app--handy .kronos-header .today-symbol { display: inline-flex; }
/* Am Handy stehen die Werkzeuge platzsparend: Icon-Knöpfe behalten ihr
   aria-label, „Termin anlegen“ bleibt der eine Primärknopf. */
.dk-app--handy .kronos-header .termin-anlegen-btn { width: var(--control-h); padding: 0; }
.dk-app--handy .kronos-header .termin-anlegen-btn :deep(.dk-ui-btn-label) { display: none; }
.dk-app--handy .kronos-header .kalender-auswahl-label { display: none; }
.dk-app--handy .kronos-header .kronos-reiter { flex: 1 1 auto; }

/* DEV-B6: Laptop-Lage (<720 px MIT Maus): die Werkzeugzeile bekommt ihre
   eigene Zeile und darf umbrechen, damit „Termin anlegen“, „⋯“ und
   „Zu prüfen“ erreichbar bleiben (Review-Punkt 5: gemessen ragten sie in
   400 px aus dem Bild). Das ist ANORDNUNG derselben Ansicht — eine
   Breiten-Regel, kein Gerüst. */
@media (max-width: 720px) {
  .kronos-header .header-right { flex-wrap: wrap; }
  .kronos-header .header-right {
    flex-wrap: wrap;
    justify-content: flex-end;
    min-width: 0;
  }
  .kronos-header .header-left { flex-wrap: wrap; }
  .kronos-reiter { flex: 1 1 auto; }
}
/* Der Umschalter der Kalenderliste gehört zur Handy-Lage (die Liste ist dort
   ein Overlay). Seit DEV-B6 ist er AUS (v-if in der Vorlage) — die
   Navigation führt der Menü-Knopf der App-Kopfzeile. Die Regel bleibt für
   den Fall, dass die Seite ihn einschaltet (`listenUmschalter`). */
.dk-app--handy .sidebar-toggle-btn { display: inline-flex; }
/* DEV-B6: In der Leisten-Lage (schmales Touchgerät, flaches Querformat) steht
   die Werkzeugzeile in einer eigenen Zeile unter der Reiterleiste — siehe
   dem Handy-Lage-Block oben am Template. Ein Maus-Laptop ohne untere Leiste
   behält die einzeilige Kopfzeile; sein Umbruch geschieht bei 1100 px. */
@media (pointer: coarse) {
  .nav-btn,
  .todaybutton,
  .termin-anlegen-btn,
  .sidebar-toggle-btn { height: 44px; }
  .nav-btn,
  .todaybutton,
  .termin-anlegen-btn { width: 44px; }
}
</style>
