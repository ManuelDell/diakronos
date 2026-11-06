/**
 * FIX-8 — Erlaubt-Liste fuer die Script-Pruefung (`script-bezeichner.mjs`).
 *
 * Ein Name in dieser Liste steht im Skript, ohne dort deklariert zu sein, und
 * ist trotzdem korrekt: Sprache, Browser-Global, Vue-Compiler-Makro oder
 * Projekt-Global. Jeder Eintrag traegt seinen Grund — der Test prueft, dass
 * keiner leer oder zu knapp ist. Ein stiller Freibrief ist nicht moeglich.
 *
 * NICHT aufgenommen (bewusst): alles, was das Projekt selbst importieren muss
 * (`vue`, `vue-router`, `pinia`, `@tabler/icons`, …). Genau solche Namen sind
 * die Fehlerklasse aus UX2d3a (`useLadeSkelett()` ohne Import) — ein
 * vergessener Import muss ein Befund bleiben. Ebenso NICHT aufgenommen:
 * zusammengesetzte Browser-Typen (`Uint8Array`, `MediaRecorder`, …) — sie
 * stehen in `ERLAUBT_ZUSAMMENGESETZT` (Klasse 2, siehe unten) nur dann,
 * wenn die Datei sie bereits ueber `globalThis.` anspricht.
 *
 * Der Test haelt zusaetzlich fest, dass KEIN Name aus dem Projekt-Code
 * (`frontend/src/diakonos/composables/ladeSkelett.mjs`, `vue`, `vue-router`)
 * in dieser Liste steht.
 */
export const ERLAUBT = new Map([
  // ── Sprache (ECMAScript) ────────────────────────────────────────────────
  ['undefined', 'Sprache: nicht gesetzt'],
  ['NaN', 'Sprache: Zahlenwert'],
  ['Infinity', 'Sprache: Zahlenwert'],
  ['Object', 'Sprache: eingebautes Objekt'],
  ['Function', 'Sprache: eingebautes Objekt'],
  ['Boolean', 'Sprache: eingebautes Objekt'],
  ['Symbol', 'Sprache: eingebautes Objekt'],
  ['Number', 'Sprache: eingebautes Objekt'],
  ['BigInt', 'Sprache: eingebautes Objekt'],
  ['Math', 'Sprache: eingebautes Objekt'],
  ['Date', 'Sprache: eingebautes Objekt'],
  ['String', 'Sprache: eingebautes Objekt'],
  ['RegExp', 'Sprache: eingebautes Objekt'],
  ['Array', 'Sprache: eingebautes Objekt'],
  ['Map', 'Sprache: eingebautes Objekt'],
  ['Set', 'Sprache: eingebautes Objekt'],
  ['WeakMap', 'Sprache: eingebautes Objekt'],
  ['WeakSet', 'Sprache: eingebautes Objekt'],
  ['JSON', 'Sprache: eingebautes Objekt'],
  ['Promise', 'Sprache: eingebautes Objekt'],
  ['Proxy', 'Sprache: eingebautes Objekt'],
  ['Reflect', 'Sprache: eingebautes Objekt'],
  ['Intl', 'Sprache: eingebautes Objekt (Datums-/Zahlformat)'],
  ['Error', 'Sprache: Fehlerklasse'],
  ['TypeError', 'Sprache: Fehlerklasse'],
  ['RangeError', 'Sprache: Fehlerklasse'],
  ['SyntaxError', 'Sprache: Fehlerklasse'],
  ['EvalError', 'Sprache: Fehlerklasse'],
  ['AggregateError', 'Sprache: Fehlerklasse (Promise.any)'],
  ['parseInt', 'Sprache: eingebaute Funktion'],
  ['parseFloat', 'Sprache: eingebaute Funktion'],
  ['isNaN', 'Sprache: eingebaute Funktion'],
  ['isFinite', 'Sprache: eingebaute Funktion'],
  ['encodeURIComponent', 'Sprache: eingebaute Funktion (Linkziele)'],
  ['decodeURIComponent', 'Sprache: eingebaute Funktion (Linkziele)'],
  ['encodeURI', 'Sprache: eingebaute Funktion'],
  ['decodeURI', 'Sprache: eingebaute Funktion'],
  ['structuredClone', 'Sprache: eingebaute Funktion'],
  ['queueMicrotask', 'Sprache: eingebaute Funktion'],
  ['globalThis', 'Sprache: globales Objekt'],
  // ── Laufzeit-Umgebung Browser (Vite-Ziel; im Frontend kein Node) ────────
  ['window', 'Browser-Global'],
  ['document', 'Browser-Global (DOM)'],
  ['location', 'Browser-Global (Adresszeile)'],
  ['history', 'Browser-Global (Verlauf)'],
  ['navigator', 'Browser-Global (Sprache, Zwischenablage)'],
  ['localStorage', 'Browser-Global (SPA-Zustand)'],
  ['sessionStorage', 'Browser-Global'],
  ['console', 'Browser-Global (Diagnose)'],
  ['alert', 'Browser-Global (Rueckmeldung)'],
  ['confirm', 'Browser-Global (Rueckfrage)'],
  ['prompt', 'Browser-Global (Eingabe)'],
  ['fetch', 'Browser-Global (API-Aufrufe)'],
  ['URL', 'Browser-Global (Linkziele)'],
  ['URLSearchParams', 'Browser-Global (Abfragezeichenkette)'],
  ['Blob', 'Browser-Global (Datei-Export)'],
  ['File', 'Browser-Global (Datei-Eingabe)'],
  ['FileReader', 'Browser-Global (Datei-Eingabe)'],
  ['FormData', 'Browser-Global (Upload)'],
  ['AbortController', 'Browser-Global (Abbruch von fetch)'],
  ['AbortSignal', 'Browser-Global (Abbruch von fetch)'],
  ['Image', 'Browser-Global (Bild vorladen)'],
  ['Event', 'Browser-Global (Ereignis)'],
  ['CustomEvent', 'Browser-Global (Ereignis)'],
  ['KeyboardEvent', 'Browser-Global (Ereignis)'],
  ['DragEvent', 'Browser-Global (Ereignis)'],
  ['MouseEvent', 'Browser-Global (Ereignis)'],
  ['ClipboardEvent', 'Browser-Global (Ereignis)'],
  ['HTMLElement', 'Browser-Global (DOM-Typ)'],
  ['Node', 'Browser-Global (DOM-Typ)'],
  ['Element', 'Browser-Global (DOM-Typ)'],
  ['CSS', 'Browser-Global (CSS.escape)'],
  ['TextEncoder', 'Browser-Global'],
  ['TextDecoder', 'Browser-Global'],
  ['DOMParser', 'Browser-Global'],
  ['XMLHttpRequest', 'Browser-Global'],
  ['MutationObserver', 'Browser-Global'],
  ['ResizeObserver', 'Browser-Global'],
  ['IntersectionObserver', 'Browser-Global'],
  ['getComputedStyle', 'Browser-Global (Farbwerte lesen)'],
  ['matchMedia', 'Browser-Global (Dunkelmodus)'],
  ['addEventListener', 'Browser-Global'],
  ['removeEventListener', 'Browser-Global'],
  ['setTimeout', 'Browser-Global (Zeitgeber)'],
  ['clearTimeout', 'Browser-Global (Zeitgeber)'],
  ['setInterval', 'Browser-Global (Zeitgeber)'],
  ['clearInterval', 'Browser-Global (Zeitgeber)'],
  ['requestAnimationFrame', 'Browser-Global (Bildtakt)'],
  ['cancelAnimationFrame', 'Browser-Global (Bildtakt)'],
  ['requestIdleCallback', 'Browser-Global (Leerlauf)'],
  ['performance', 'Browser-Global (Messung)'],
  ['crypto', 'Browser-Global (Zufall/Pruefsumme)'],
  ['btoa', 'Browser-Global (Base64)'],
  ['atob', 'Browser-Global (Base64)'],
  ['self', 'Browser-Global (in Modulen nicht deklariert)'],
  ['postMessage', 'Browser-Global (Fenster-Nachricht)'],
  // ── Vue-Compiler-Makros (`<script setup>`, teils nur `lang="ts"`) ───────
  ['defineProps', 'Vue-Compiler-Makro (wird ersetzt, ist keine Variable)'],
  ['defineEmits', 'Vue-Compiler-Makro (wird ersetzt, ist keine Variable)'],
  ['defineExpose', 'Vue-Compiler-Makro (wird ersetzt, ist keine Variable)'],
  ['defineOptions', 'Vue-Compiler-Makro (wird ersetzt, ist keine Variable)'],
  ['defineModel', 'Vue-Compiler-Makro (wird ersetzt, ist keine Variable)'],
  ['defineSlots', 'Vue-Compiler-Makro (wird ersetzt, ist keine Variable)'],
  ['withDefaults', 'Vue-Compiler-Makro (nur mit lang="ts")'],
  // ── Testdateien (Node-Lauf, nicht Browser) ──────────────────────────────
  // `src/**/*.test.mjs` laufen unter `node --test`; dort sind `Buffer` und
  // `process` Node-Globals. Sie stehen hier NICHT, weil die Erlaubt-Liste
  // fuer Anwendungscode gilt — die Testdateien sind von der Pruefung
  // ausgenommen (siehe `istTestdatei` in `script-bezeichner.mjs`).
])

/**
 * Klasse 2: zusammengesetzte Browser-Typen. Sie sind im Browser global, im
 * Node-Test nicht immer — und ein `new Uint8Array(…)` ohne Deklaration ist
 * genau derselbe Fehler wie `useLadeSkelett()` ohne Import. Deshalb gilt:
 * diese Namen sind NUR erlaubt, wenn die Datei sie bereits ueber
 * `globalThis.<Name>` anspricht (das macht die Abhaengigkeit sichtbar und
 * laesst den Node-Test denselben Weg gehen). Die Pruefung meldet sonst
 * `Uint8Array` mit dem Hinweis „globalThis.Uint8Array“.
 */
export const ERLAUBT_ZUSAMMENGESETZT = new Map([
  ['Uint8Array', 'zusammengesetzter Browser-Typ — als globalThis.Uint8Array schreiben'],
  ['Uint8ClampedArray', 'zusammengesetzter Browser-Typ — als globalThis.Uint8ClampedArray schreiben'],
  ['Int8Array', 'zusammengesetzter Browser-Typ — als globalThis.Int8Array schreiben'],
  ['Int32Array', 'zusammengesetzter Browser-Typ — als globalThis.Int32Array schreiben'],
  ['Float32Array', 'zusammengesetzter Browser-Typ — als globalThis.Float32Array schreiben'],
  ['ArrayBuffer', 'zusammengesetzter Browser-Typ — als globalThis.ArrayBuffer schreiben'],
  ['MediaRecorder', 'zusammengesetzter Browser-Typ — als globalThis.MediaRecorder schreiben'],
  ['AudioContext', 'zusammengesetzter Browser-Typ — als globalThis.AudioContext schreiben'],
  ['AudioBuffer', 'zusammengesetzter Browser-Typ — als globalThis.AudioBuffer schreiben'],
  ['BlobEvent', 'zusammengesetzter Browser-Typ — als globalThis.BlobEvent schreiben'],
  ['PointerEvent', 'zusammengesetzter Browser-Typ — als globalThis.PointerEvent schreiben'],
  ['TouchEvent', 'zusammengesetzter Browser-Typ — als globalThis.TouchEvent schreiben'],
  ['InputEvent', 'zusammengesetzter Browser-Typ — als globalThis.InputEvent schreiben'],
  ['SubmitEvent', 'zusammengesetzter Browser-Typ — als globalThis.SubmitEvent schreiben'],
  ['FocusEvent', 'zusammengesetzter Browser-Typ — als globalThis.FocusEvent schreiben'],
  ['DOMRect', 'zusammengesetzter Browser-Typ — als globalThis.DOMRect schreiben'],
  ['Range', 'zusammengesetzter Browser-Typ — als globalThis.Range schreiben'],
  ['NodeList', 'zusammengesetzter Browser-Typ — als globalThis.NodeList schreiben'],
  ['HTMLInputElement', 'zusammengesetzter Browser-Typ — als globalThis.HTMLInputElement schreiben'],
  ['HTMLTextAreaElement', 'zusammengesetzter Browser-Typ — als globalThis.HTMLTextAreaElement schreiben'],
  ['HTMLSelectElement', 'zusammengesetzter Browser-Typ — als globalThis.HTMLSelectElement schreiben'],
  ['HTMLDivElement', 'zusammengesetzter Browser-Typ — als globalThis.HTMLDivElement schreiben'],
  ['HTMLCanvasElement', 'zusammengesetzter Browser-Typ — als globalThis.HTMLCanvasElement schreiben'],
  ['MediaQueryList', 'zusammengesetzter Browser-Typ — als globalThis.MediaQueryList schreiben'],
  ['DOMException', 'zusammengesetzter Browser-Typ — als globalThis.DOMException schreiben'],
  ['StorageEvent', 'zusammengesetzter Browser-Typ — als globalThis.StorageEvent schreiben'],
  ['MessageEvent', 'zusammengesetzter Browser-Typ — als globalThis.MessageEvent schreiben'],
  ['Response', 'zusammengesetzter Browser-Typ — als globalThis.Response schreiben'],
  ['Request', 'zusammengesetzter Browser-Typ — als globalThis.Request schreiben'],
  ['Headers', 'zusammengesetzter Browser-Typ — als globalThis.Headers schreiben'],
  ['ReadableStream', 'zusammengesetzter Browser-Typ — als globalThis.ReadableStream schreiben'],
  ['setImmediate', 'Node-Global — im Browser nicht vorhanden, nicht verwenden'],
])
