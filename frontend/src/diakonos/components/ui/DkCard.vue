<template>
  <section class="dk-ui-card">
    <header v-if="title || $slots.header || $slots.actions" class="dk-ui-card-kopf">
      <slot name="header">
        <h2 v-if="title" class="dk-ui-card-titel">{{ title }}</h2>
      </slot>
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
 */
defineProps({
  title: { type: String, default: '' },
  // flach: kein Innenabstand (z. B. für Tabellen, die selbst randlos sind)
  flach: Boolean,
})
</script>

<style scoped>
.dk-ui-card {
  background: var(--surface);
  border: var(--karte-rand) solid var(--rahmen-farbe);
  border-radius: var(--radius-lg);
  box-shadow: var(--schatten-karte);
  overflow: hidden;
}
.dk-ui-card-kopf {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  flex-wrap: wrap;
  padding: var(--karte-innen) var(--karte-innen) 0;
}
.dk-ui-card-titel {
  font-size: var(--fs-h3);
  font-weight: 600;
  margin: 0;
  color: var(--text);
}
.dk-ui-card-aktionen { display: flex; align-items: center; gap: var(--sp-2); }
.dk-ui-card-koerper { padding: var(--karte-innen); }
.dk-ui-card-koerper.is-flach { padding: 0; }
/* Mit Kopf sitzt der Körper unter dem Titel — der Abstand kommt aus dem
   Kopf (padding-bottom 0 + gap unten), damit Titel und Inhalt eine Gruppe
   bilden und nicht durch eine Linie getrennt werden. */
.dk-ui-card-kopf + .dk-ui-card-koerper { padding-top: var(--sp-3); }
.dk-ui-card-fuss {
  padding: var(--sp-3) var(--karte-innen) var(--karte-innen);
  background: var(--surface-2);
}
</style>
