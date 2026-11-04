# Platzhalter für `diakronos_app.gestaltung` (Karte UX1a)

Dieses Verzeichnis enthält **noch keine** Fachlogik. Es existiert, damit der
Frontend-Stage des Images (`backend/Dockerfile`, Regel 13) eine Quelle für
seine bedingte Kopie hat:

    COPY backend/src/diakronos_app/gestaltung/ /ux1a-backend/gestaltung/

## Warum es diesen Platzhalter gibt

Der Wächter `frontend/tests/ux1a-abstand-tokens.test.mjs` (T4) prüft, dass die
Standardwerte der Gestaltungs-Einstellungen in
`gestaltung/tokens.py` — entstanden in Karte **UX1j** — zu den Werten in
`frontend/src/diakonos/tokens.css` passen. Ohne diesen Vergleich könnten
Oberfläche und Server auseinanderlaufen: die Einstellungen zeigten 24 px an,
während die Oberfläche 20 px zeichnet.

UX1j lag zum Zeitpunkt von UX1a noch auf seinem eigenen Branch
(`wt/t_a1a03439`), nicht in `main`. Ein `COPY` auf einen fehlenden Pfad bricht
den Docker-Build ab (gemessen), deshalb liegt hier ein Platzhalter statt einer
Lücke.

## Verhalten

* **UX1j noch nicht gemergt:** `tokens.py` fehlt. Der Test meldet das
  ausdrücklich („Drift-Prüfung übersprungen") und besteht — es gibt keine
  zweite Wertquelle, also auch nichts zu vergleichen.
* **UX1j gemergt:** `tokens.py` liegt hier, der Test liest ihn über
  `UX1A_BACKEND` und schlägt bei jeder Abweichung fehl.

## Aufräumen

Sobald UX1j in `main` liegt, kann diese README gelöscht werden; das
Verzeichnis füllt sich dann mit dem echten Paket. Die `COPY`-Zeile im
Dockerfile bleibt in beiden Fällen richtig.
