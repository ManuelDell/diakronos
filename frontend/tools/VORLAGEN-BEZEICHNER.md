# Vue-Vorlagen: Prüfung auf ungebundene Bezeichner (FIX-7)

Werkzeug und Wächter liegen **in** `frontend/` und kommen mit dem normalen
Frontend-Build mit — keine eigene `COPY`-Zeile in `backend/Dockerfile`
(Regel 13 bleibt erfüllt: nichts außerhalb von `frontend/`).

| Datei | Zweck |
|---|---|
| `frontend/tools/vorlagen-bezeichner.mjs` | Werkzeug: kompiliert jede `.vue` mit `@vue/compiler-sfc`, sammelt die Template-Ausdrücke und meldet freie Namen, die im Skript nicht gebunden sind. |
| `frontend/tests/fix7-vorlagen-bezeichner.test.mjs` | Wächter über **alle** `.vue` unter `frontend/src` (plus Gegenproben, die ein Wiederauftauchen von `fmtDate` sofort zeigen). |
| `backend/Dockerfile` | Der Test steht in der `node --test`-Liste des Frontend-Stage (`tests/fix7-*.test.mjs`). |

## Abhängigkeiten

`@vue/compiler-sfc` (mit `vue` 3.5.44) und `@babel/parser` (7.29.9) kommen
ohne eigene Angabe in `frontend/package.json` mit — sie stehen
transitiv im `package-lock.json`. Der Test bricht mit „Cannot find package",
falls eine Umstellung sie entfernt; dann bitte als echte
`devDependency` eintragen, statt den Test abzuschalten.

## Aufruf

```sh
cd frontend
node --test tests/fix7-vorlagen-bezeichner.test.mjs    # einzelner Wächter
docker build -f backend/Dockerfile --target frontend .  # Nachweis im Image
```

## Melden und Ausnahmen

Ein Befund zeigt `Datei: Name1, Name2`. Ausnahmen stehen ausschließlich in
`ERLAUBT` (`tools/vorlagen-bezeichner.mjs`) und tragen dort ihren **Grund**
(Sprache, Vue-Globals wie `$emit`/`$attrs`, vue-router-Globals `$router`/`$route`;
global registrierte Komponenten gibt es nicht). Der Test prüft, dass jeder
Eintrag eine Begründung hat — ein stiller Freibrief ist nicht möglich.
