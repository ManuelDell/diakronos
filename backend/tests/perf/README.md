PERF-K3 — Messwerkzeuge (nur Messung, kein Fix)
================================================

Zweck: die Kalender-Startaufrufe LIVE auf Postgres messen (PERF-K2 senkte
die Zahl im Test auf 1203; live war sie nie gemessen).

Dateien
-------
  fabrik.py               Testdaten in realistischer Größe: 26 Gruppen,
                          14 Kalender, 134 Mitglieder, 2000 Termine
                          (+ 240 Serienfolgen). Verteilt auf 6 Rollen.
  messung.py              Messlauf: SQL-Abfragen je Endpunkt
                          (`before_cursor_execute`) + Antwortzeit
                          (Median aus N Läufen) + Top-10-Wiederholer mit
                          Herkunft (Stack-Auszug bis diakronos_app).
  messung_k4a.py          PERF-K4a-Nachmessung: NUR `get_kanban_board_data`,
                          je Rolle Admin/HV/Mitglied (gleiche Technik). Damit
                          wurde die Zahl dieser Karte vorher/nachher belegt.
  test_perf_k3_waechter.py  Hält Messwerkzeuge aus der normalen Suite
                          (Marker `perf`, per Default deselektiert).

Aufruf (eigener Wegwerf-Stack, NIE der Betrieb)
-----------------------------------------------
  cd <repo>
  docker compose -p perfk3 --env-file <env> -f compose/perfk3.yml up -d db redis
  docker compose -p perfk3 ... run --rm --no-deps app \
      alembic -c /app/alembic.ini upgrade head
  docker compose -p perfk3 ... run --rm --no-deps \
      -v "$PWD/backend/tests/perf:/app/tests/perf:ro" \
      -e PYTHONPATH=/app/src:/app/tests/perf app \
      python /app/tests/perf/messung.py --laeufe 5

Danach `docker compose -p perfk3 ... down -v` (Stack restlos abbauen).

Gemessene Endpunkte (Reihenfolge aus Kalender.vue `onMounted`):
  1. get_accessible_calendars   (store.fetchAccessibleCalendars)
  2. get_kalender_verwaltung    (kalenderVerwaltungLaden, parallel)
  3. get_current_user_context   (benutzerKontextLaden)
  4. get_moderation_count       (offeneZahlLaden, nur bei darfPruefen)
  5. get_kanban_board_data      (pruefIdsLaden, Prüf-Spalte)
  6. get_calendar_events        (Raster-Feed, KronosCalendar eventSources)

WICHTIG (Messgenauigkeit)
-------------------------
Je Messung wird EIN `merkungsrahmen` geöffnet — im Betrieb tut das
`RequestContextMiddleware` je Request. Ohne Rahmen wäre die Zahl geschönt
(anders als PERF-K1 keine Vorwärmung: jede Messung startet mit leerem Merker).
