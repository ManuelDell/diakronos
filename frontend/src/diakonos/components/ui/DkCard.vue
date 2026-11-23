<template>
  <section class="dk-ui-card" :class="{ 'is-flach': flach, 'is-zeile': zeile }" :id="anker ? ankerId : undefined">
    <header v-if="title || sub || $slots.header || $slots.actions" class="dk-ui-card-kopf">
      <div class="dk-ui-card-kopftext">
        <slot name="header">
          <!-- DES-1b (Review 4): Kennzeichen und Titel stehen in EINER Zeile.
               Der Slot `vor-titel` (z. B. der Farbpunkt einer Kalenderzeile)
               liegt deshalb in der Titelzeile — nicht im Spaltenblock, sonst
               stünde der Punkt über dem Titel. Die Unterzeile steht darunter
               über die volle Textbreite. -->
          <div class="dk-ui-card-titelzeile">
            <span v-if="$slots['vor-titel']" class="dk-ui-card-vor">
              <slot name="vor-titel" />
            </span>
            <!-- DES-1 (Review 6): ein abgeschnittener Titel braucht den vollen
                 Text als `title`-Attribut — sonst ist er nur noch gekürzt lesbar.
                 DES-1 (Review 2): die Überschriftsebene ist wählbar (`ebene`),
                 weil eine Zeile in einer Karte eine Ebene tiefer steht (h3). -->
            <component :is="`h${ebene}`" v-if="title" class="dk-ui-card-titel" :title="title">{{ title }}</component>
          </div>
          <p v-if="sub" class="dk-ui-card-sub">{{ sub }}</p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="dk-ui-card-aktionen">
        <slot name="actions" />
      </div>
    </header>
    <div class="dk-ui-card-koerper" :class="{ 'is-flach': flach }">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="dk-ui-card-fuss">
      <slot name="footer" />
    </footer>
  </section>
</template>

<script setup>
/**
 * DkCard — ruhige Fläche mit optionalem Kopf, Aktionen und Fuß (Stil A).
 * Nur Tokens, keine festen Farben.
 *
 * UX1d (D1): Die Karte hat KEINEN Rahmen und KEINE Kopflinie mehr. Sie
 * trennt sich über ihre getönte Fläche und den sanften Kartenschatten
 * (--schatten-karte) vom Grund — Prinzip Ä2 „Abstand/getönte Fläche/sanfter
 * Schatten statt Linien und Kästen“. Der Kopf trägt den Titel in normaler
 * Schreibung (16 px/600), nicht mehr in Versalien-Grau; Kopf und Körper
 * liegen auf derselben Fläche, getrennt nur durch Abstand (Prinzip S3).
 *
 * Die Breite eines Rahmens kommt aus der Gestaltungs-Einstellung
 * (--karte-rand, Standard 0 = kein Rahmen): wer in den Einstellungen einen Rahmen
 * wählt, bekommt ihn hier — ohne dass die Komponente einen eigenen Wert
 * kennt.
 *
 * DES-1 (Befund Manuel 17.11.): Titel wie „Rollen der Gruppe“ brachen auf der
 * Gruppenseite unnötig auf zwei Zeilen um, obwohl die Karte breit war. Ursache
 * war der Kartenkopf selbst: `justify-content: space-between` quetschte den
 * Titel (er war kein eigenes Flex-Kind, sondern lag nackt neben dem
 * Aktionsbereich) auf seine längste Wortbreite, und `flex-wrap: wrap` setzte
 * den Aktionsbereich trotz freier Zeile in Zeile 2. Jetzt gilt: der Text
 * (Titel + Unterzeile, `sub`) sitzt in EINEM eigenen Feld, das wächst und
 * schrumpfen darf (`flex: 1 1 auto; min-width: 0`), die Aktionen stehen
 * daneben. Der Titel bleibt einzeilig, solange Platz ist
 * (`white-space: nowrap` + `text-overflow: ellipsis` — ganze Wörter brechen
 * erst, wenn wirklich kein Platz mehr ist), die Unterzeile steht UNTER dem
 * Titel über die volle Textbreite. Am Handy (390 px) bekommen die Aktionen
 * ihre eigene Zeile (Media Query im Kopf), damit der Titel die Breite allein
 * hat.
 *
 * Review-Nacharbeit (6/7/2):
 * - `title`-Attribut am Titel: ein per Ellipse abgeschnittener Titel bleibt
 *   über den Tooltip vollständig lesbar.
 * - `flex-wrap: wrap` am Kopf ist zurück, aber erst wenn der Platz WIRKLICH
 *   fehlt (Textfeld `flex: 1 1 12rem`): Köpfe mit mehreren Abzeichen (etwa
 *   `Registrierung`) quetschen den Titel nicht mehr, breite Köpfe bleiben
 *   einzeilig.
 * - Eigenschaft `ebene` (Standard 2): eine Zeile innerhalb einer Karte bekommt
 *   `:ebene="3"` — h3 statt eines zweiten h2.
 *
 * DES-1b (Review 4), zwei Nacharbeiten am Kartenkopf:
 * - Der Slot `vor-titel` liegt in EINER Titelzeile mit der Überschrift
 *   (`.dk-ui-card-titelzeile`, flex row). Vorher stand er im Spaltenblock und
 *   damit in eigener Zeile ÜBER dem Titel (am Handy mittig darüber).
 * - Eigenschaft `zeile`: eine Zeile IN einer anderen Karte gibt ihre
 *   Kopf-Polsterung ab (Titel und aufgeklappter Inhalt bündig, nichts doppelt
 *   gepolstert). Bewusst getrennt von `flach` — `flach` tragen auch
 *   eigenständige Seitenleisten-Karten, deren Titel am Rand klebte.
 */
const props = defineProps({
  title: { type: String, default: '' },
  /**
   * DES-1: Unterzeile direkt unter dem Titel — die Beschreibung einer Karte
   * gehört strukturell in den Kopf (über die volle Textbreite), nicht als
   * erster Absatz in den Körper neben einen daneben liegenden Aktionsbereich.
   */
  sub: { type: String, default: '' },
  /**
   * DES-1 (Review 2): Überschriftsebene des Titels (2 = Standard). Eine Zeile
   * INNERHALB einer Karte (z. B. eine Kalenderzeile in „Kalender der Gruppe“)
   * ist eine Ebene tiefer: `:ebene="3"` macht aus dem h2 ein h3 — die
   * Gliederung bleibt lesbar, statt zwei h2 zu stapeln.
   */
  ebene: {
    type: [Number, String],
    default: 2,
    // Nur echte Überschriftsebenen unterhalb des Seitenkopfs: h2 (Karte),
    // h3 (Zeile in einer Karte), h4 (Zeile in einer Zeile). Alles andere
    // (etwa `ebene="7"`) ergäbe ein Element ohne Gliederungswert.
    validator: (v) => [2, 3, 4].includes(Number(v)),
  },
  // flach: kein Innenabstand des KÖRPERS (z. B. für Tabellen, die selbst
  // randlos sind). Kein Ersatz für „Seitenleisten-Karte“ — siehe `zeile`.
  flach: Boolean,
  /**
   * DES-1b (Review 4): `zeile` heißt „diese Karte IST eine Zeile in einer
   * anderen Karte“ (z. B. ein Kalender in „Kalender der Gruppe“). Nur dann
   * gibt der KOPF seine Karteninnen-Polsterung ab, damit Titel und
   * aufgeklappter Inhalt bündig stehen und in der äußeren Karte nichts
   * doppelt gepolstert wird.
   *
   * Bewusst NICHT an `flach` gekoppelt: `flach` tragen auch eigenständige
   * Karten mit Fläche und Schatten (Seitenleisten in Beiträge und Wiki,
   * `title` + `flach` ohne `zeile`) — dort klebte der Titel am Kartenrand.
   */
  zeile: Boolean,
  /**
   * UX3h: Sprungmarke dieser Karte (`dk-sprung-<anker>`) — für Abschnitte, die
   * kein einzelnes Feld, sondern eine ganze Karte meinen (z. B. „Rundungen“
   * oder „Authentik-Gruppen und Rollen“). Kennung aus `pages/sprung.mjs`.
   */
  anker: { type: String, default: '' },
})
import { computed } from 'vue'
import { sprungId } from '../../pages/sprung.mjs'

const ankerId = computed(() => sprungId(props.anker))
</script>

<style scoped>
.dk-ui-card {
  background: var(--surface);
  border: var(--karte-rand) solid var(--rahmen-farbe);
  border-radius: var(--radius-lg);
  box-shadow: var(--schatten-karte);
  overflow: hidden;
}
/* DES-1: Titel und Aktionen stehen nebeneinander, der Text bekommt den
   verfügbaren Platz — kein `space-between` (das presste den Titel auf seine
   längste Wortbreite). `flex-wrap: wrap` bleibt, ABER erst wenn der Platz
   wirklich fehlt (Review 7: ein Kopf mit zwei Abzeichen und ein Titel in einer
   300-px-Karte brauchen das): das Textfeld hat eine Mindestbreite von 12 rem,
   darunter rutscht der Aktionsbereich in die nächste Zeile statt den Titel zu
   quetschen. Auf breiten Köpfen bleibt der Titel einzeilig. */
.dk-ui-card-kopf {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--karte-innen) var(--karte-innen) 0;
}
/* DES-1b (Review 4): `zeile` heißt „dieser Baustein ist eine Zeile IN einer
   anderen Karte“ — nur dann gibt der KOPF seine Karteninnen-Polsterung ab,
   damit Titel und aufgeklappter Inhalt bündig stehen und in der äußeren Karte
   nichts doppelt gepolstert wird. Eine Stelle für beide Teile.
   Früher hing das an `flach`; das trafen auch eigenständige Karten mit Fläche
   und Schatten (Seitenleisten in Beiträge/Wiki) — dort klebte der Titel am
   Kartenrand. `flach` regelt jetzt nur noch den KÖRPER (siehe unten). */
.dk-ui-card.is-zeile .dk-ui-card-kopf { padding: 0; }
.dk-ui-card-kopftext {
  /* Ä3/S3: Titel und Unterzeile bilden EINE Gruppe; der Abstand zwischen
     Kopf und Körper ist größer (--sp-3) als der zwischen Titel und
     Unterzeile (--sp-1). */
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  /* `flex: 1 1 12rem` gibt dem Text allen freien Platz und erlaubt das
     Schrumpfen bis 12 rem; `min-width: 0` ist das Sicherheitsnetz für ein
     einzelnes überlanges Wort (ohne das sprengt es den Kopf). */
  flex: 1 1 12rem;
  min-width: 0;
}
/* DES-1b (Review 4): Kennzeichen und Titel in EINER Zeile — der Punkt (Slot
   `vor-titel`, z. B. der Farbpunkt eines Kalenders) steht links NEBEN dem
   Titel, beide mittig auf derselben Linie. Vorher lag der Punkt im
   Spaltenblock (`.dk-ui-card-kopftext`, flex-direction: column) und stand
   damit in eigener Zeile ÜBER dem Titel. Steht kein Punkt im Slot, ist das
   Feld leer und der Titel nimmt die volle Breite. */
.dk-ui-card-titelzeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.dk-ui-card-vor {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
}
.dk-ui-card-titel {
  font-size: var(--fs-h3);
  font-weight: var(--fw-fett);
  margin: 0;
  color: var(--text);
  /* DES-1: einzeilig, solange Platz ist. */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-ui-card-sub {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-sm);
  /* Unterzeile über die volle Textbreite; lange Wörter dürfen umbrechen. */
  overflow-wrap: anywhere;
}
.dk-ui-card-aktionen {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  /* Die Aktionen behalten ihre natürliche Breite — sie schrumpfen nicht
     zugunsten des Titels. */
  flex: 0 0 auto;
}
.dk-ui-card-koerper { padding: var(--karte-innen); }
/* BEF-DESIGN-1: `flach` nimmt NUR dem Körper den Abstand, der Kopf behält
   seinen. Für Seitenleisten-Karten deshalb NICHT `flach` verwenden — sonst
   steht der Titel gepolstert und der Inhalt klebt am Kartenrand. */
.dk-ui-card-koerper.is-flach { padding: 0; }
/* Mit Kopf sitzt der Körper unter dem Titel — der Abstand kommt aus dem
   Kopf (padding-bottom 0 + gap unten), damit Titel und Inhalt eine Gruppe
   bilden und nicht durch eine Linie getrennt werden. */
.dk-ui-card-kopf + .dk-ui-card-koerper { padding-top: var(--sp-3); }
.dk-ui-card-fuss {
  padding: var(--sp-3) var(--karte-innen) var(--karte-innen);
  background: var(--surface-2);
}
/* DES-1 · Handy: die Aktionen bekommen ihre eigene Zeile unter dem TITEL
   (nicht unter der Unterzeile), damit der Titel die volle Breite hat.
   `order` statt Umbau im DOM — die Tab-Reihenfolge bleibt gleich. */
@media (max-width: 720px) {
  .dk-ui-card-kopf {
    flex-wrap: wrap;
    align-items: flex-start;
  }
  .dk-ui-card-kopftext { flex-basis: 100%; }
  /* Einzeilig bleibt der Titel nur, wo er auch passt: bei Ellipse ginge am
     Handy der halbe Titel verloren, deshalb bricht er hier wieder (ganze
     Wörter). */
  .dk-ui-card-titel { white-space: normal; overflow: visible; }
  /* DES-1b (Review 4): Punkt und Titel bleiben auch am Handy in EINER Zeile
     (der Punkt bekommt nie die volle Breite). `center` richtet ihn auf die
     Titelzeile aus — bei einem mehrzeiligen Titel steht er damit mittig
     daneben, was bei einem kleinen Quadrat ruhiger wirkt als ein Kantensprung.
     Kein eigener Versatz: der Punkt ist höhenmäßig kleiner als eine Zeile. */
  .dk-ui-card-titelzeile { align-items: center; }
}
</style>
