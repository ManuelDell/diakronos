<template>
  <details class="pr-legende">
    <summary><span class="pr-legende-pfeil" aria-hidden="true">▸</span>Zeichen in diesem Plan erklärt</summary>
    <ul class="pr-legende-liste">
      <li>
        <span class="pr-legende-zeichen" aria-hidden="true">📌</span>
        <span><strong>Von Hand festgelegt:</strong> Diesen Wert hast du selbst eingetragen. Der Vorschlag lässt ihn unverändert.</span>
      </li>
      <li>
        <span class="pr-legende-zeichen pr-legende-leer" aria-hidden="true">(leer)</span>
        <span><strong>(leer):</strong> An dieser Stelle ist noch kein Wert eingetragen.</span>
      </li>
    </ul>
  </details>
</template>
<script setup>
/** Sichtbare Legende fuer 📌 (von Hand festgelegt) und (leer) (UX C6). */
</script>
<style scoped>
.pr-legende { margin: 0 0 var(--sp-3); font-size: var(--fs-12); color: var(--dk-text-muted); }
.pr-legende > summary { cursor: pointer; display: flex; align-items: center; gap: var(--sp-1); width: fit-content; }
.pr-legende-pfeil { display: inline-block; transition: transform 120ms ease; }
.pr-legende[open] > summary .pr-legende-pfeil { transform: rotate(90deg); }
.pr-legende-liste { list-style: none; margin: var(--sp-2) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.pr-legende-liste li { display: flex; align-items: baseline; gap: var(--sp-2); }
.pr-legende-zeichen { flex-shrink: 0; min-width: 40px; }
.pr-legende-leer { font-family: var(--font-mono); color: var(--dk-text-subtle); }
</style>
