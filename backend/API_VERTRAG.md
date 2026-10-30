# API-Vertrag — Diakronos Standalone (abgeleitet aus der SPA)

Dieses Dokument ist die **verbindliche** Beschreibung dessen, was die bestehende
SPA (`referenz/diakronos-frappe/frontend/`) vom Backend erwartet. Es ist NICHT
erfunden, sondern am Client-Code abgelesen. Wo SPA und Frappe-Konvention
auseinandergehen, **gewinnt die SPA**, und der Widerspruch ist hier vermerkt.

Quellen (gelesen):
- `frontend/src/diakonos/composables/useApi.js` — zentraler `apiCall`/`apiGet`
- `frontend/src/diakonos/**` — Auswertung der Antworten
- `diakronos/public/js/**` — `fetch`-Aufrufe im Kronos-Teil

---

## 1. `/api/method/{dotted_path}` — der Hauptzustand

### Erfolg

`apiCall()` (POST) und `apiGet()` (GET) lesen **ausschliesslich** `data.message`:

```js
const data = await res.json()
if (!res.ok) throw new Error(data?.message || data?.exception || `HTTP ${res.status}`)
if (data.exc)  throw new Error(data.exc)
return data.message          // <-- der Rueckgabewert der Python-Funktion
```

Envelope bei Erfolg (HTTP 200):

```json
{ "message": <Rueckgabewert der Funktion> }
```

Der Wert unter `message` ist **beliebig** (Objekt, Liste, Skalar) — die SPA
greift z. B. auf `message.total`, `message.data`, `message.gruppen`,
`message.anmeldungen.gesamt` zu. Der Envelope ist damit derselbe wie bei
Frappe (`{"message": ...}`), aber der Inhalt wird 1:1 durchgereicht.

### Fehler — zwei Ebenen

**a) HTTP-Fehler (nicht-2xx):** Die SPA liest in dieser Reihenfolge
`data.message` → `data.exception` → `"HTTP <status>"` und wirft einen `Error`.
Das Backend setzt fuer Fehler, die `frappe.throw(...)` entsprechen, den
HTTP-Status **417 (Expectation Failed)** — das ist Frappes Konvention und wird
von der SPA nicht anders erwartet (`!res.ok` faengt jeden nicht-2xx).
Body:

```json
{ "message": "<Klartextmeldung>", "exception": "<Exc-Klasse>", "exc_type": "<Exc-Klasse>" }
```

**a1) `exc_type`/`exception` nur nach Allowlist (SEC-8/S2, Pentest R3-A):**
Das Feld traegt **nicht** mehr den internen Python-Klassennamen, sondern nur
noch einen der drei Werte, die die SPA tatsaechlich auswertet:

| Wert | Wo die SPA ihn liest |
|---|---|
| `CSRFTokenError` (417) | `shared/sitzung-pruefen.js` → `istSitzungsAbbruch`: Sitzung neu aufbauen statt Fachfehler zeigen |
| `SessionExpired` (401) | dieselbe Stelle; 401/419 gelten als Sitzungsende |
| `PermissionError` (403) | Rechte-Anzeige (`useApi.js`, `MitgliedDetail.vue`) — kein Sitzungs-Neuaufbau |

**Alle anderen** Fehler tragen `exception` = `exc_type` = `"Error"`. Die
Meldung (`message`) bleibt der Fachtext; der echte Klassenname geht ins Log
(`diakronos_app.frappe_compat.router`, Level INFO). Die Allowlist steht als
`EXC_TYPEN_ALLOWLIST` in `frappe_compat/router.py` und ist per Test
festgenagelt (`backend/tests/test_sec8_exception_allowlist.py`) — sie darf nur
wachsen, wenn das Frontend den neuen Wert auch auswertet.

**b) `exc` im 200er-Body:** Der Client prueft zusaetzlich `data.exc` und wirft
daraus. Wir liefern `exc` nur, wenn wir es bewusst setzen (Audit-Pfad); fuer den
Normalfall genuegt `message` + HTTP-Status.

**c) Diagnosetexte bleiben im Log (SEC-7/S1+S2):** Fehlerantworten des
Method-Routers enthalten NIE eine Python-Signatur, einen internen
Funktionsnamen oder eine Exception-Klasse aus unerwarteten Ausnahmen. Konkret
(alle Zeilen mit `exc_type` = `"Error"`, siehe a1):

| Fall | Status | Body |
|---|---|---|
| fehlende/falsche/unerwartete Argumente (`TypeError`, `ValueError`, `KeyError`, auch falsche Typen) | `417` | `{"message": "Ungueltige Anfrage", "exception": "Error", "exc_type": "Error"}` |
| unbekannter Methodenname **und** unzulaessiger Pfad (`..`, `/`, `\`, `%`, Leerzeichen, leeres Segment) | `404` | `{"message": "Methode nicht gefunden", "exception": "Error", "exc_type": "Error"}` |
| unerwarteter Fehler in der Fachfunktion | `500` | `{"message": "Interner Fehler", "exception": "Error", "exc_type": "Error"}` — Traceback nur im Log |
| fachlicher Fehler (`frappe.throw` → `FrappeCompatError`, z. B. `ValidationError`, `DoesNotExistError`) | `exc.http_status` | `message` = Fachtext, `exception`/`exc_type` = `"Error"` (ausser den drei Allowlist-Werten) |

Der Methodenpfad wird **vor** jeder Aufloesung gegen eine Whitelist geprueft:
`[A-Za-z0-9_]+` in Segmenten, getrennt durch genau einen Punkt, max. 255
Zeichen. Damit ist weder Methoden- noch Signatur-Enumeration ueber
unterschiedliche Fehlerbilder moeglich, und Pfad-Traversal endet in einem
sauberen 404 statt in einem 500.

**Sonderfall Audit (`AuditConfirmationRequired`):** nicht Teil von P2a. Wenn in
`message`/`exc` der String `CONFIRM_REQUIRED:` vorkommt, parst die SPA die
Policy. Diese Ausnahme wird erst in einer spaeteren Karte bedient; der Router
darf `message`/`exc` aber nicht umschreiben.

### Parameteruebergabe — alle vorkommenden Faelle

1. **POST mit JSON-Body** (`apiCall`): `Content-Type: application/json`,
   Body = die Argumente als JSON-Objekt. Header `X-Frappe-CSRF-Token` wird
   mitgeschickt (Wert vorerst irrelevant, echte Auth spaeter).
2. **GET mit Query-String** (`apiGet`): `?a=1&b=2`, `undefined`/`null` werden
   ausgelassen.
3. **POST mit `Content-Type: application/json`** direkt per `fetch` (Kronos,
   Profil, Dashboard) — identisch zu (1).
4. **`FormData`** (`/api/method/upload_file`) — Datei-Upload, **nicht** Teil von
   P2a; der Router muss aber Body-Parsing fuer JSON **und** Form tolerieren.

Der Router nimmt daher: JSON-Body (dict) **oder** Form-Body **oder**
Query-String, in dieser Prioritaet, und uebergibt die Werte als Keyword-Argumente
an die Zielfunktion.

---

## 2. `/api/resource/{doctype}` und `/api/resource/{doctype}/{name}`

**Widerspruch SPA ↔ Frappe (dokumentiert):**

Frappes echte `/api/resource`-Antwort ist fuer Listen ein **nacktes JSON-Array**
(die Dokumente direkt), fuer ein Einzeldokument ein **nacktes Objekt**. Die SPA
liest aber:

```js
// KronosEventEdit.vue / KronosEventCreate.vue
categories.value = catRes.data || []     // <-- erwartet {"data": [...]}
```

→ **Die SPA gewinnt.** `GET /api/resource/{doctype}` liefert den Envelope
`{"data": [ ...dokumente... ]}`. Grund: der Client wurde gegen eine
Wrapper-Schicht gebaut, nicht gegen Frappe-Roh. Das weicht bewusst von Frappe ab.

- `GET /api/resource/{doctype}` → `200 {"data": [ {...}, {...} ]}`
  - Query-Parameter wie in Frappe: `fields` (JSON-Liste oder `*`),
    `filters` (JSON), `limit_page_length`, `limit_start`, `order_by`.
- `GET /api/resource/{doctype}/{name}` → `200 {"data": {...}}`
- `POST /api/resource/{doctype}` → `200 {"data": {...neu...}}`
- `PUT /api/resource/{doctype}/{name}` → `200 {"data": {...}}`
- `DELETE /api/resource/{doctype}/{name}` → `202 {"data": {}}`
  - Der einzige DELETE-Aufruf (`useEventsApi.js`) prueft nur `res.ok`, ignoriert
    den Body — Form egal, Hauptsache 2xx.
- Unbekannter DocType → `404` im Fehlerformat aus §1.

---

## 3. Was NICHT geschluckt werden darf

- `GET /healthz` — bestehender Endpunkt (P0), muss unveraendert 200 liefern.
- Die spaetere SPA-Auslieferung (statische Pfade `/`, `/assets/...`, SPA-Fallback).
  Der `/api/`-Router wird deswegen **nur** unter `/api/` gemountet.

---

## 4. Zusammenfassung der Envelope-Formen

| Route | Erfolg | Fehler |
|---|---|---|
| `/api/method/<path>` | `{"message": <wert>}` | non-2xx, `{"message","exception"}` |
| `/api/resource/<dt>` | `{"data": [...]}` (SPA-Abweichung) | 404/417, Fehlerformat |
| `/api/resource/<dt>/<name>` | `{"data": {...}}` | 404/417, Fehlerformat |
| `/healthz` | unveraendertes P0-Objekt | — |

`throw(msg, exc)` in der Compat-Schicht wird vom Router in das Fehlerformat
uebersetzt: HTTP **417**, Body `{"message": str(msg), "exception": excname}`.

---

## 5. Frappe-Core-APIs (P2c) — nachgebildet, mit Belegen

Diese drei Endpunkte gehoeren zu Frappe selbst (nicht zur Diakronos-App) und
fehlten deshalb in jeder Portierungsvorlage. Alle drei sind unter
`/api/method/...` registriert (`backend/src/diakronos_app/api/frappe_core.py`).

### `POST /api/method/logout`

Aufrufer: `public/js/builder/header_build_elements.js:184`,
`public/js/psalmos/header_build.js:102`, `public/js/shared/header.js:163`.
Die SPA schickt nur `X-Frappe-CSRF-Token` (Wert irrelevant) und prueft danach
lediglich, dass die Antwort ok ist — kein Redirect, kein Reload, kein
Feldzugriff. Antwort daher bewusst Frappe-kompatibel:

```json
{"message": {"message": "Logged out", "user": "Guest", "previous_user": "Administrator"}}
```

`previous_user` ist die Session-Kennung *vor* dem Logout und wird fuer die
Audit-Spur gebraucht. `user` ist danach `Guest`. **Einschraenkung (dokumentiert,
gewollt):** es gibt noch keine echte Anmeldung (P3-nachgelagert); die
Platzhalter-Session liefert als Benutzer `Administrator`, es wird also nur
deren serverseitiger Zustand verworfen. Sobald echte Auth existiert, aendert
sich nur die Herkunft von `previous_user`.

### `POST /api/method/frappe.client.insert`

Aufrufer: kein SPA-Aufrufer mehr. Bis P2-5 legte
`frontend/src/diakonos/pages/Registrierung.vue` (heute
`pages/einstellungen/Registrierung.vue`) den Registrierungslink so an; heute
laeuft das ueber `diakronos.diakonos.api.registrierungslink_api.create_link`.
Der Endpunkt bleibt fuer direkte/Altaufrufer bestehen.
Body: `{"doc": { "doctype": "...", "feld": wert, ... }}`.
`doc` wird sowohl als JSON-Objekt (JSON-Body) **als auch** als JSON-*String*
(Form-Body) akzeptiert. Antwort ist der angelegte Datensatz unter `message`:

```json
{"message": {"name": "...", "doctype": "...", ... alle Felder ...}}
```

**Permission ist Pflicht und fail-closed.** Nicht jeder DocType ist
insertierbar: der Aufruf laeuft durch `frappe_compat.permissions`. Ohne
Mitgliederadministrator-Rolle:

```json
HTTP 403
{"message": "Nur fuer Mitgliederadministratoren.", "exception": "PermissionError", "exc_type": "PermissionError"}
```

Das ist ausdruecklich so gewollt (Mitgliederdaten): lieber 403 als offen.
Bewusst **kein** generisches Insert fuer beliebige DocTypes ohne Pruefung.

### `POST /api/method/upload_file`

Aufrufer: `frontend/src/diakonos/pages/Profile.vue:465`.
Multipart-FormData, die SPA sendet genau:

| Feld | Wert | Anmerkung |
|---|---|---|
| `file` | Blob + Dateiname | der eigentliche Upload |
| `is_private` | `'0'` | wird von der SPA immer explizit gesendet |
| `folder` | `'Home/Attachments'` | rein informativ, siehe unten |

Die SPA liest **nur** `json.message?.file_url` und schickt diese URL danach an
`profile.update_profile_picture`. Antwort:

```json
{"message": {"name": "...", "file_name": "profilbild.jpg",
             "file_url": "/files/<sha256>-profilbild.jpg",
             "is_private": false, "file_size": 12345, "content_hash": "<sha256>"}}
```

**Speicherort:** `settings.files_dir` (Default `/data/files`), als Bind-Mount
`./data/files` in `docker-compose.yml` fuer `app` **und** `worker` — gleicher
Baum, damit der Worker Anhaenge sieht. Der vom Client gelieferte `folder`-Wert
wird **nie** als Pfad uebernommen.

**Sicherheit (nicht verhandelbar, mit Tests belegt):**

- **Path-Traversal:** Dateiname wird auf den reinen Basisnamen reduziert und
  saemtliche Pfadtrenner/`..`-Sequenzen entfernt. Belegt mit drei echten
  Uploads (siehe Test `test_traversal_*`): `../../etc/passwd` → gespeichert als
  `...-passwd` **innerhalb** `/data/files/`; `../../etc/shadow` (URL-kodiert) →
  `...-2F.._2Fetc_2Fshadow`; `folder=../../../etc` wird komplett ignoriert.
  `/etc/passwd` blieb nachweislich unveraendert.
- **Groessenlimit:** `settings.max_upload_bytes` (Default 10 MB). Darueber →
  HTTP 417 `{"message": "Datei zu gross (...)", "exception": "ValidationError"}`.
- **Content-Type** wird erkannt (Endung + Deklaration), aber der Dateiname
  bestimmt ausschliesslich das Ziel — der Client kann kein Ziel erzwingen.
- **`is_private`-Default ist `true`** (fail-safe) — weicht bewusst von Frappes
  `false` ab: fehlt das Feld, darf eine Mitgliederdatei nicht versehentlich
  oeffentlich werden. Die SPA sendet es ohnehin immer explizit.

**Widerspruch SPA ↔ Frappe (dokumentiert):** Frappe legt Dateien unter
`/files/...` bzw. `/private/files/...` ab und liefert je nach `is_private` einen
anderen Praefix. Diese Implementierung liefert **immer** `/files/` und legt
`is_private` nur als Metadatum im `File`-Dokument ab (siehe unten). Grund:
die SPA unterscheidet beim Ausliefern nicht, und ein privater Pfad ohne
Auslieferungs-Schutz waere eine Scheinsicherheit. Sobald es eine geschuetzte
Auslieferung gibt, wird der Praefix hier nachgezogen.

### `File`-DocType

Neu als Frappe-Core-Stub in `models/core.py` (`FileModel`, Tabelle `file`),
erzeugt ueber `tools/gen_models.py` (CORE_STUBS). Felder: `name` (PK),
`file_name`, `file_url`, `file_size`, `is_private`, `content_hash`,
`folder`, `attached_to_doctype`, `attached_to_name`, `attached_to_field` sowie
die Standard-Spalten. Migration:
`alembic/versions/p2c_file_tabelle.py` (`down_revision = "3f4d296602ab"`).
Hinweis: es gibt daneben die app-eigene DocType `SichererAnhang` — die ist
**nicht** dasselbe und bleibt unberuehrt.

### `/api/resource/Element` und `/api/resource/Eventkategorie`

Der generische Router aus P2a deckt beide ab; es war **keine** Ergaenzung
noetig. Belegte Aufrufe und ihre Parameter:

- `GET /api/resource/Eventkategorie?fields=["name","event_category_name","hat_ablaufplan"]&limit_page_length=500`
  (`KronosEventCreate.vue:327`, `KronosEventEdit.vue:309`, `modal_create.js:21`)
  → `{"data": [...]}`.
- `GET /api/resource/Element?fields=["name",...]&limit_page_length=3`
  (`events_api.js:142`, `useEventsApi.js:103`, `modal_edit.js:23`) → `{"data": []}`.

Beide liefen im Live-Test mit `fields` + `limit_page_length` direkt durch.
Abweichungen gab es **keine** — der `{"data": ...}`-Envelope aus §2 passt. Eine
Einschraenkung sei ehrlich genannt: unbekannte Feldnamen werden abgewiesen
(HTTP 417, z. B. `Element: unbekanntes Feld 'bezeichnung'`) — das ist gewollt
(kein stiller Fallback) und deckt sich mit dem Diff aus P1d.

### Verifikation (Live, echte Ausgaben)

Gegen ein echtes uvicorn auf Port 8123/8124 mit der echten Postgres-DB:
`insert` → 200 + Zeile in `eventkategorie`; `insert` ohne Rolle → 403
(fail-closed); `logout` → 200 mit obigem Envelope; `upload_file` → 200 mit
`file_url`, Datei auf Platte **und** Zeile in `file`; drei Traversal-Versuche
→ alle neutralisiert; `>10 MB` → 417; `Eventkategorie`/`Element` mit
`fields`+`limit_page_length` → 200. Test-Suite: **113 passed / 6 skipped / 0 failed**
(3x randomisiert stabil).

---

## REG-1a — Registrierung: Startdatum, Beschreibung, Bilder (Manuel 23.10.)

Alle Wege, ueber die ein BESUCHER einen Registrierungslink benutzt, sprechen
dieselbe Fachpruefung (`api/registrierung._validate_token`). Neues Feld:
`registrierungslink.gueltig_ab` (DATE, `NULL` = sofort gueltig). Vor diesem Tag
ist der Link fuer Besucher gesperrt, Administratoren sehen ihn weiter.

### `GET /api/method/diakronos.diakonos.api.registrierung.validate_token`

Zusaetzliche Felder in `message` (die bisherigen bleiben unveraendert):

| Feld | Typ | Bedeutung |
|---|---|---|
| `beschreibung` | string | Beschreibung des Formulars, bereinigter reiner Text (kein HTML, Markdown-Betonungen entfernt) |
| `banner_bild` | string | relativer Abrufpfad `/public/registrierung/<token>/bild/banner` oder `""` |
| `hintergrund_bild` | string | relativer Abrufpfad `/public/registrierung/<token>/bild/hintergrund` oder `""` |

Vor `gueltig_ab` antwortet der Endpunkt wie bei einem abgelaufenen Link:

```json
HTTP 403
{"message": "Anmeldung ab 26.10.2026 möglich.", "exception": "PermissionError", "exc_type": "PermissionError"}
```

Derselbe Text erscheint auf der ausgelieferten Seite als
`window.__diakronos.linkFehler`; `submit_registrierung` und `submit_gast`
verweigern identisch. Am Tag selbst (und danach) ist der Link nutzbar.

### `GET /api/method/diakronos.diakonos.api.registrierung.get_oeffentliche_formular`

Anzeige-Endpunkt fuer das Formular (Felder + Kopf in einem Aufruf), ebenfalls
oeffentlich:

```json
{"message": {"typ": "Mitglied-Registrierung", "bezeichnung": "Einladung",
             "gueltig_ab": "2026-10-26", "felder": [...], "mit_kinder": 1,
             "mit_gaesten": 0, "beschreibung": "...",
             "banner_bild": "/public/registrierung/<token>/bild/banner",
             "hintergrund_bild": ""}}
```

Ist der Aufrufer Administrator (Rolle geprueft, nicht vom Client geglaubt),
wird die Startdatum-Pruefung uebersprungen — die Verwaltung muss einen noch
nicht gueltigen Link ansehen koennen. Ein unbekannter oder abgeschalteter
Token bleibt auch dann ein Fehler (403).

### `GET /public/registrierung/<token>/bild/<banner|hintergrund>`

Das Bild selbst (`inline`, `Cache-Control: public, max-age=300`,
`X-Content-Type-Options: nosniff`). Oeffentlich, aber NUR mit gueltigem
Registrierungstoken und nur fuer Rasterbilder (PNG/JPEG/GIF/WebP, aus den
Magic-Bytes bestimmt). `GET /files/<name>` verlangt weiter eine Anmeldung —
die Formularbilder sind am Formular vorbei nicht abrufbar.

### Verwaltung (nur Mitgliederadministratoren)

`create_link`/`update_link` (`registrierungslink_api`) nehmen `gueltig_ab`
(`JJJJ-MM-TT`, leer = sofort); `update_link` schreibt ein leeres Datum
ausdruecklich auf `NULL`. Antworten enthalten `gueltig_ab`. Der Zustand der
Linkliste (`admin_hub.get_anmeldungen_hub`) kennt zusaetzlich
`"bevorstehend": true` (vor `gueltig_ab`) und `"gueltig_ab": "JJJJ-MM-TT"`.

**Zeitraum-Pruefung.** `gueltig_ab` muss vor `gueltig_bis` liegen; sonst
HTTP 417 mit beiden Daten im Text (`„Gültig ab“ (…) liegt nach „gültig bis“
(…)`). Beim `update_link` wird der jeweils andere Wert aus dem Bestand
herangezogen, wenn er im Aufruf fehlt.

**Zeitzone.** „Heute“ ist der Tag in `settings.calendar_timezone`
(Default `Europe/Berlin`, ENV `CALENDAR_TIMEZONE`) — nicht der Tag des
Containers. Anzeige (`registrierungslink.zustand`) und Wirkung
(`_validate_token`) benutzen dieselbe Quelle
(`anmeldung/registrierungslink.heute_gemeinde`), damit ein Link nicht in der
einen Ansicht „bevorstehend“ und in der anderen „aktiv“ ist.

`admin_hub.update_anmeldeformular` erweitert um:

| Parameter | Bedeutung |
|---|---|
| `beschreibung` | Text des Formulars; normalisiert gespeichert, **Klartext** (leer = `NULL`) |
| `banner_bild_datei` / `hintergrund_bild_datei` | Dateiname einer vorher per `upload_file` hochgeladenen Datei; geprueft wird der `File`-Datensatz (Herkunft), die Privatablage und das Rasterbild (sonst 417) |
| `bilder_entfernen` | Komma-Liste `banner,hintergrund` → Spalte leeren **und Datei + `File`-Datensatz loeschen** |

**Beschreibung ist Klartext.** Gespeichert und ausgeliefert wird der reine
Text (Markdown-Betonungen entfernt, Steuerzeichen entfernt, hoechstens 5000
Zeichen). `<` und `>` bleiben **Zeichen im Text** — auch der HTML-Anfang
`<script>` steht wortgetreu drin. Das Escaping macht ausschliesslich die
Anzeige (`{{ }}` in `registrierung/App.vue`, nie `v-html`); der Server maskiert
NICHT, sonst laese der Besucher woertlich `&lt;`.

**Bild-Lebenszyklus.** Zulaessig ist nur eine Datei aus dem Formular-Upload:
es muss einen `File`-Datensatz zu genau diesem Dateinamen geben, er darf keine
private Datei eines anderen Mitglieds sein (`is_private` mit fremdem
Eigentuemer bzw. `/private/files/…`), und die Magic-Bytes muessen ein
Rasterbild sein. Wird ein Bild ersetzt, per `bilder_entfernen` entfernt oder
das Formular geloescht (`delete_anmeldeformular`), werden **Datei und
`File`-Datensatz** mitgeloescht — sofern kein anderes Formular dieselbe Datei
noch fuehrt (geteilte Uploads bleiben erhalten).

`admin_hub.get_anmeldeformular_kopf` liefert Bezeichnung, Schalter,
`beschreibung`, `bannerbild`/`hintergrundbild` (Dateiname) sowie
`banner_bild_url`/`hintergrund_bild_url` (`/files/<name>` fuer die Vorschau der
Verwaltung).
