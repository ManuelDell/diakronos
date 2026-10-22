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
.pr-legende { margin: 0 0 14px; font-size: .8rem; color: var(--dk-text-muted); }
.pr-legende > summary { cursor: pointer; display: flex; align-items: center; gap: 6px; width: fit-content; }
.pr-legende-pfeil { display: inline-block; transition: transform 120ms ease; }
.pr-legende[open] > summary .pr-legende-pfeil { transform: rotate(90deg); }
.pr-legende-liste { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.pr-legende-liste li { display: flex; align-items: baseline; gap: 8px; }
.pr-legende-zeichen { flex-shrink: 0; min-width: 40px; }
.pr-legende-leer { font-family: monospace; color: var(--dk-text-subtle); }
</style>
