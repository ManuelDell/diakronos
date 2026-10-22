# Frontend prüfen

Node 22 und die Abhängigkeiten aus `package-lock.json` sind erforderlich, auch
für Tests, die Vue-Komponenten kompilieren. Vom Projektverzeichnis aus:

```sh
cd frontend
npm ci --legacy-peer-deps --no-audit --no-fund
node --test src/diakonos/components/planrahmen/*.test.mjs tests/planrahmen-*.test.mjs
npm run build
```

Ohne lokale Node-Installation im Wegwerf-Container (kein Betriebsstack):

```sh
docker run --rm -v "$PWD:/source:ro" node:22-alpine sh -c '
  mkdir -p /work/frontend /work/backend
  cp -a /source/frontend/. /work/frontend/
  cp -a /source/backend/src /work/backend/
  cd /work/frontend
  npm ci --legacy-peer-deps --no-audit --no-fund
  node --test src/diakonos/components/planrahmen/*.test.mjs tests/planrahmen-*.test.mjs
'
```

Der zweite Aufruf erfolgt vom Projektverzeichnis, nicht aus `frontend/`.
Die Backend-Beispiele werden von mehreren Frontend-Prüfungen mitgelesen.
Der vollständige Docker-Build (`backend/Dockerfile`) führt dieselben
Planrahmen-Tests vor dem SPA-Build aus.
