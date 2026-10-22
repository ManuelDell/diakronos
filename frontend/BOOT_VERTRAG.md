# BOOT-VERTRAG — `window.__DIakonosBOOT`

Vertrag zwischen Backend und der Diakonos-SPA. Dies ist die Spezifikation für
den späteren echten Endpunkt.

## Name — exakt so

```js
window.__DIakonosBOOT
```

**Das große `I` in `DIakonos` ist korrekt und kein Tippfehler.** Der Bezeichner
lautet `__DIakonosBOOT` (zwei führende Unterstriche, `DI`, `akonos`, `BOOT`).

Quelle im SPA-Code (alle Fundstellen):

```
frontend/src/diakonos/composables/useSession.js:4
frontend/src/diakonos/composables/useApi.js:18
frontend/src/diakonos/composables/useApi.js:105
frontend/src/diakonos/router.js:144
frontend/src/diakonos/composables/useKronosStore.js:46
frontend/src/diakonos/composables/useWidgetData.js:19
frontend/src/diakonos/components/AppSidebar.vue:125
frontend/src/diakonos/components/kronos/ModerationSidebar.vue:51
frontend/src/diakonos/components/mini/MiniCalendarWidget.vue:29
```

Original-Erzeuger (Referenz-Repo): `diakronos/www/diakonos/index.html:23` und
`diakronos/www/diakonos/index.py`.

## Zeitpunkt — kritisch

`useSession.js` liest das Objekt **einmal beim Modul-Import**, auf oberster
Ebene:

```js
const boot = window.__DIakonosBOOT || {}     // useSession.js:4
```

Das `import` des Entry-Bundles durch das `<script type="module">` löst diese
Zeile aus. **Das Boot-Objekt muss zwingend VOR dem Entry-`<script>` im HTML
stehen.** Ein asynchrones Nachladen (fetch beim App-Start) ist nicht
ausreichend — dann ist `useSession()` bereits mit leeren Werten initialisiert.
Andere Stellen lesen dagegen live bei Bedarf (`useApi.js` bei jedem Call), die
sind unkritisch.

## Struktur

```jsonc
{
  "user_fullname": "Test Nutzer",           // string
  "user_email":    "test@example.invalid",  // string
  "user_image":    "",                      // string (URL, darf leer sein)
  "csrf_token":    "dummy-csrf-token",      // string
  "is_admin":      true,                    // boolean
  "mitglied": {                             // object ODER null
    "name":     "MITGLIED-0001",            // string  (technische ID)
    "vorname":  "Test",                     // string
    "nachname": "Nutzer",                   // string
    "status":   "Aktiv"                     // string  ("Gast" | sonst)
  },
  "modules": []                            // array<object>
}
```

### `modules` — A1c5: Feld `route` zeigt in die SPA

`modules` war hier als `array<string>` beschrieben, obwohl der Server
schon seit A1b2-rest Objekte liefert (`get_accessible_modules()`). Die
Beschreibung ist korrigiert: `modules` ist ein **Array von Objekten**.

Seit A1c5 gilt fuer jedes Objekt:

| Feld | Typ | Wirkung |
|---|---|---|
| `module_name` | string | Modulname (`"Kronos"`) |
| `prefix` | string | Konfigurations-Praefix (`"kronos"`) |
| `anzeige_name` | string | Beschriftung |
| `icon` | string | Icon-URL |
| `route` | string, **optional** | ZIEL DER SPA, hash-relativ (`"#/kalender"`) |

**Warum `route` optional ist:** Der Wert zeigte urspruenglich auf Frappe-www-
Seiten (`/app/kronos`, `/kronos`, `/psalmos`), die dieser Stack nicht ausliefert
— jeder Klick endete in einem 404. Seit A1c5 zeigt er auf die SPA. Zwei Module
haben dort keine Seite (`Diakronos` = Frappe-Workspace, `Seelsorge` = eigene
App); fuer sie **fehlt der Schluessel ganz** — nicht `null`, nicht ein toter
Link. Ein Aufrufer muss `route` daher als optional behandeln (`m.route` erst
nach einer Existenzpruefung benutzen).

**Warum hash-relativ (`#/kalender`) und nicht `/diakonos#/kalender`:** Beide
gaengigen Aufrufer tragen damit: `navigate(route)` macht aus allem ohne `#` ein
`#<pfad>` (ein Praefix ergaebe das kaputte `#/diakonos#/kalender`), und
`<a :href="route">` loest relativ gegen die aktuelle URL auf. Ein hash-relativer
Wert kann nie einen 404 erzeugen, weil er das Dokument nie verlaesst.

### Feld-Herkunft und Verwendung (aus dem SPA-Code verifiziert)

| Feld | Typ | Gelesen in | Wirkung |
|---|---|---|---|
| `user_fullname` | string | `useSession.js:8` | Anzeigename (Sidebar/Topbar) |
| `user_email` | string | `useSession.js:9` | E-Mail des Nutzers |
| `user_image` | string | `useSession.js:10` | Avatar-URL |
| `csrf_token` | string | `useApi.js:18,105`, `useKronosStore.js:46`, `useWidgetData.js:19`, `MiniCalendarWidget.vue:29` | Header `X-Frappe-CSRF-Token` bei `apiCall`/`apiGet` |
| `is_admin` | boolean | `useSession.js:11`, `router.js:146` | Admin-Rechte; **Route-Guard**: Admin darf alles |
| `mitglied` | object\|null | `useSession.js:13`, `router.js:145,149` | `mitglied.status === 'Gast'` schränkt Routen ein |
| `modules` | array | `useSession.js:14` | Freigeschaltete Sidebar-Module |
| `church_name` | string (optional) | `AppSidebar.vue:125`, `ModerationSidebar.vue:51` | Gemeindename; Fallback `'Meine Gemeinde'` |
| `logo_url` | string\|null (optional) | `AppSidebar.vue:126`, `ModerationSidebar.vue:52` | Logo; Fallback `null` |

### Nicht im Original-Erzeuger, aber von der SPA gelesen

`church_name` und `logo_url` werden von der SPA gelesen, stehen aber **nicht**
im Boot-Objekt von `index.html:23-31`. Die SPA hat Fallbacks, läuft also ohne
sie — allerdings mit generischem Namen. Der spätere echte Endpunkt **sollte
beide Felder mitliefern**.

### `mitglied.status` und der Gast-Guard

`router.js:138-154` implementiert einen Route-Guard:

- kein `mitglied` → kein Guard
- `modules`/Rollen egal
- `mitglied.status === 'Gast'` → nur `#/`, `#/kalender`, `#/profile` erlaubt
- sonst → alles erlaubt

Der Dummy-Wert `"Aktiv"` umgeht den Guard, `""` würde ihn ebenfalls umgehen
(nur `'Gast'` triggert). Für einen realistischen Test des Guards eignet sich
`"Gast"`.

## Was der Dummy aktuell liefert

Definiert in `backend/src/diakronos_app/spa.py` als `DUMMY_BOOT`, injiziert von
`render_index()` in die ausgelieferte `index.html`:

```js
window.__DIakonosBOOT = {"user_fullname": "Test Nutzer", "user_email": "test@example.invalid", "user_image": "", "csrf_token": "dummy-csrf-token", "is_admin": true, "mitglied": {"name": "MITGLIED-0001", "vorname": "Test", "nachname": "Nutzer", "status": "Aktiv"}, "modules": []}
```

## Anforderungen an den späteren echten Endpunkt

1. Der Endpunkt, der `/diakonos` ausliefert, erzeugt das Boot-Objekt
   **serverseitig im HTML** — nicht per separatem Fetch.
2. Reihenfolge im HTML: `<script>window.__DIakonosBOOT = {…};</script>` **vor**
   `<script type="module" src="…/diakonos-<hash>.js">`.
3. `csrf_token` muss ein **echter** Session-CSRF-Token sein, sonst schlagen
   alle `POST /api/method/…` mit 400 fehl (`useApi.js:28`).
4. `mitglied` kommt aus der `Mitglied`-DocType-Suche über `user_email` (siehe
   Referenz `diakronos/www/diakonos/index.py:28-33`). Nicht gefunden → `null`.
5. `is_admin` = Rolle `Mitgliederadministrator` **oder** `System Manager`
   (Referenz `index.py:37`).
6. `modules` = Ergebnis von `get_accessible_modules()`
   (Referenz `index.py:42-43`); im Fehlerfall leere Liste, nie `null`.
7. `church_name` / `logo_url` ergänzen.
8. `json.dumps` muss die Werte HTML-sicher escapen (`</script>` in Freitext!) —
   im Dummy irrelevant, im echten Betrieb ein XSS-Vektor.
