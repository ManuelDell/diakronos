# API-VERTRAG — Diakonos Vue-3-SPA

> **Automatisch erzeugt aus dem SPA-Quellcode** (`frontend/src/`, 90 Dateien).
> Jeder Aufruf erfolgt ueber `apiCall(method, args)` aus
> `frontend/src/diakonos/composables/useApi.js`, das `POST /api/method/<method>`
> gegen die eigene Origin schickt.

## WICHTIG: Diese Liste stammt NICHT aus Aufrufliste des Frappe-Frontends

Aufrufliste des Frappe-Frontends beschreibt das **legacy Frappe-Frontend**
(`diakronos/public/js/**` — 67 Aufrufe, 31 distinkte Pfade). Die **Vue-SPA ruft
dagegen 78 distinkte Methoden** auf. Die Inventar-Liste ist fuer die
Endpunkt-Portierung daher **nicht ausreichend** — sie deckt nur einen Teil ab
(im Wesentlichen `diakronos.kronos.api.*`). Massgeblich ist die Liste unten.

## Aufruf-Konvention

```
POST /api/method/<method>
Header: X-Frappe-CSRF-Token: <window.__DIakonosBOOT.csrf_token>
Body:   JSON (args)
Antwort: Frappe-Konvention — bei Fehlern { exc, _server_messages }; sonst Rohdaten
```

Zusaetzlich genutzt: `POST /api/method/upload_file` (Datei-Upload, mehrteilig)

## Uebersicht nach Modul

| Modul | Endpunkte |
|---|---|
| `diakronos.diakonos.api.admin_hub` | 7 |
| `diakronos.diakonos.api.audit` | 1 |
| `diakronos.diakonos.api.auswahl` | 4 |
| `diakronos.diakonos.api.beitraege` | 6 |
| `diakronos.diakonos.api.dienstplan` | 1 |
| `diakronos.diakonos.api.gruppen` | 18 |
| `diakronos.diakonos.api.kalender` | 1 |
| `diakronos.diakonos.api.mitglieder` | 5 |
| `diakronos.diakonos.api.planung` | 11 |
| `diakronos.diakonos.api.registrierungslink_api` | 3 |
| `diakronos.diakonos.api.ressourcen` | 6 |
| `diakronos.diakonos.api.session` | 1 |
| `diakronos.diakonos.api.wiki` | 5 |
| `diakronos.diakronos.api.ressourcen` | 1 |
| `diakronos.kronos.api.permissions` | 1 |
| `diakronos.kronos.api.ressource_api` | 1 |
| `diakronos.kronos.api.series` | 2 |
| `diakronos.psalmos.api.musik` | 4 |
| **Gesamt** | **78** |

---

## `diakronos.diakonos.api.admin_hub`

### `create_anmeldeformular`
- **Vollpfad:** `diakronos.diakonos.api.admin_hub.create_anmeldeformular`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:473`

### `genehmige_anmeldung`
- **Vollpfad:** `diakronos.diakonos.api.admin_hub.genehmige_anmeldung`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:391`

### `get_anmeldeformulare`
- **Vollpfad:** `diakronos.diakonos.api.admin_hub.get_anmeldeformulare`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:379`

### `get_anmeldungen_hub`
- **Vollpfad:** `diakronos.diakonos.api.admin_hub.get_anmeldungen_hub`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:367`

### `get_statistik`
- **Vollpfad:** `diakronos.diakonos.api.admin_hub.get_statistik`
- Aufruf: `frontend/src/diakonos/pages/Statistik.vue:67`

### `lehne_anmeldung_ab`
- **Vollpfad:** `diakronos.diakonos.api.admin_hub.lehne_anmeldung_ab`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:408`

### `update_anmeldeformular_felder`
- **Vollpfad:** `diakronos.diakonos.api.admin_hub.update_anmeldeformular_felder`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:489`

## `diakronos.diakonos.api.audit`

### `mark_notifications_read`
- **Vollpfad:** `diakronos.diakonos.api.audit.mark_notifications_read`
- Aufruf: `frontend/src/diakonos/composables/useNotifications.js:20`

## `diakronos.diakonos.api.auswahl`

### `get_inhalt_optionen`
- **Vollpfad:** `diakronos.diakonos.api.auswahl.get_inhalt_optionen`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:738`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:1147`

### `get_kalender_optionen`
- **Vollpfad:** `diakronos.diakonos.api.auswahl.get_kalender_optionen`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:502`

### `get_ressourcen_optionen`
- **Vollpfad:** `diakronos.diakonos.api.auswahl.get_ressourcen_optionen`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:1375`

### `get_sammlungen`
- **Vollpfad:** `diakronos.diakonos.api.auswahl.get_sammlungen`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:511`

## `diakronos.diakonos.api.beitraege`

### `create_beitrag`
- **Vollpfad:** `diakronos.diakonos.api.beitraege.create_beitrag`
- Aufruf: `frontend/src/diakonos/pages/Beitraege.vue:352`

### `create_kommentar`
- **Vollpfad:** `diakronos.diakonos.api.beitraege.create_kommentar`
- Aufruf: `frontend/src/diakonos/pages/Beitraege.vue:382`

### `delete_beitrag`
- **Vollpfad:** `diakronos.diakonos.api.beitraege.delete_beitrag`
- Aufruf: `frontend/src/diakonos/pages/Beitraege.vue:369`

### `get_beitraege_liste`
- **Vollpfad:** `diakronos.diakonos.api.beitraege.get_beitraege_liste`
- Aufruf: `frontend/src/diakonos/pages/Beitraege.vue:262`

### `get_beitrag_detail`
- **Vollpfad:** `diakronos.diakonos.api.beitraege.get_beitrag_detail`
- Aufruf: `frontend/src/diakonos/pages/Beitraege.vue:270`

### `update_beitrag`
- **Vollpfad:** `diakronos.diakonos.api.beitraege.update_beitrag`
- Aufruf: `frontend/src/diakonos/pages/Beitraege.vue:345`

## `diakronos.diakonos.api.dienstplan`

### `get_meine_dienste`
- **Vollpfad:** `diakronos.diakonos.api.dienstplan.get_meine_dienste`
- Aufruf: `frontend/src/diakonos/pages/Dienstplan.vue:160`

## `diakronos.diakonos.api.gruppen`

### `add_mitglied_to_gruppe`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.add_mitglied_to_gruppe`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:611`

### `create_ankuendigung`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.create_ankuendigung`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:590`

### `create_aufgabe`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.create_aufgabe`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:556`

### `create_dienstbereich`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.create_dienstbereich`
- Aufruf: `frontend/src/diakonos/pages/Organigramm.vue:252`

### `create_gruppe`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.create_gruppe`
- Aufruf: `frontend/src/diakonos/pages/Organigramm.vue:257`

### `create_untergruppe`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.create_untergruppe`
- Aufruf: `frontend/src/diakonos/pages/Organigramm.vue:262`

### `get_gruppe_detail`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.get_gruppe_detail`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:478`

### `get_gruppen_for_orgchart`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.get_gruppen_for_orgchart`
- Aufruf: `frontend/src/diakonos/pages/Organigramm.vue:379`

### `get_gruppen_hierarchie`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.get_gruppen_hierarchie`
- Aufruf: `frontend/src/diakonos/pages/Statistik.vue:66`

### `get_gruppen_page_data`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.get_gruppen_page_data`
- Aufruf: `frontend/src/diakonos/pages/Gruppen.vue:192`

### `get_untergruppe_detail`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.get_untergruppe_detail`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:483`

### `get_user_create_permissions`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.get_user_create_permissions`
- Aufruf: `frontend/src/diakonos/pages/Organigramm.vue:380`

### `remove_mitglied_from_gruppe`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.remove_mitglied_from_gruppe`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:634`

### `toggle_aufgabe`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.toggle_aufgabe`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:572`

### `update_dienstbereich`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.update_dienstbereich`
- Aufruf: `frontend/src/diakonos/pages/Organigramm.vue:290`

### `update_gruppe`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.update_gruppe`
- Aufruf: `frontend/src/diakonos/pages/Organigramm.vue:286`

### `update_mitglied_rolle`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.update_mitglied_rolle`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:655`

### `update_untergruppe`
- **Vollpfad:** `diakronos.diakonos.api.gruppen.update_untergruppe`
- Aufruf: `frontend/src/diakonos/pages/Organigramm.vue:288`

## `diakronos.diakonos.api.kalender`

### `get_events`
- **Vollpfad:** `diakronos.diakonos.api.kalender.get_events`
- Aufruf: `frontend/src/diakonos/pages/GruppeDetail.vue:496`

## `diakronos.diakonos.api.mitglieder`

### `get_adressbuch`
- **Vollpfad:** `diakronos.diakonos.api.mitglieder.get_adressbuch`
- Aufruf: `frontend/src/diakonos/pages/Adressbuch.vue:81`

### `get_mitglied_detail`
- **Vollpfad:** `diakronos.diakonos.api.mitglieder.get_mitglied_detail`
- Aufruf: `frontend/src/diakonos/pages/MitgliedDetail.vue:379`

### `get_mitglieder_liste`
- **Vollpfad:** `diakronos.diakonos.api.mitglieder.get_mitglieder_liste`
- Aufruf: `frontend/src/diakonos/composables/useMitglieder.js:24`
- Aufruf: `frontend/src/diakonos/pages/Statistik.vue:65`

### `update_mitglied`
- **Vollpfad:** `diakronos.diakonos.api.mitglieder.update_mitglied`
- Aufruf: `frontend/src/diakonos/pages/MitgliedDetail.vue:421`
- Aufruf: `frontend/src/diakonos/pages/MitgliedDetail.vue:438`

### `widerruf_einwilligung`
- **Vollpfad:** `diakronos.diakonos.api.mitglieder.widerruf_einwilligung`
- Aufruf: `frontend/src/diakonos/pages/Dsgvo.vue:89`
- Aufruf: `frontend/src/diakonos/pages/MitgliedDetail.vue:474`
- Aufruf: `frontend/src/diakonos/pages/MitgliedDetail.vue:487`

## `diakronos.diakonos.api.planung`

### `create_plan`
- **Vollpfad:** `diakronos.diakonos.api.planung.create_plan`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:583`

### `generiere_rotation`
- **Vollpfad:** `diakronos.diakonos.api.planung.generiere_rotation`
- Aufruf: `frontend/src/diakonos/components/planung/TerminLeiste.vue:77`

### `get_besetzungsmatrix`
- **Vollpfad:** `diakronos.diakonos.api.planung.get_besetzungsmatrix`
- Aufruf: `frontend/src/diakonos/pages/PlanDetail.vue:302`

### `get_plaene`
- **Vollpfad:** `diakronos.diakonos.api.planung.get_plaene`
- Aufruf: `frontend/src/diakonos/pages/Plaene.vue:136`

### `get_plan_uebersicht`
- **Vollpfad:** `diakronos.diakonos.api.planung.get_plan_uebersicht`
- Aufruf: `frontend/src/diakonos/components/planung/TerminLeiste.vue:66`
- Aufruf: `frontend/src/diakonos/pages/PlanDetail.vue:273`

### `get_positionen`
- **Vollpfad:** `diakronos.diakonos.api.planung.get_positionen`
- Aufruf: `frontend/src/diakonos/pages/PlanDetail.vue:274`

### `get_teilnehmer`
- **Vollpfad:** `diakronos.diakonos.api.planung.get_teilnehmer`
- Aufruf: `frontend/src/diakonos/pages/PlanDetail.vue:299`

### `get_vorlagen`
- **Vollpfad:** `diakronos.diakonos.api.planung.get_vorlagen`
- Aufruf: `frontend/src/diakonos/pages/PlanDetail.vue:275`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:491`

### `speichere_plan_entwurf`
- **Vollpfad:** `diakronos.diakonos.api.planung.speichere_plan_entwurf`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:1312`

### `veroeffentliche_plan`
- **Vollpfad:** `diakronos.diakonos.api.planung.veroeffentliche_plan`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:1344`

### `zurueckziehen_plan`
- **Vollpfad:** `diakronos.diakonos.api.planung.zurueckziehen_plan`
- Aufruf: `frontend/src/diakonos/pages/PlanWizard.vue:1359`

## `diakronos.diakonos.api.registrierungslink_api`

### `create_link`
- **Vollpfad:** `diakronos.diakonos.api.registrierungslink_api.create_link`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:425`

### `delete_link`
- **Vollpfad:** `diakronos.diakonos.api.registrierungslink_api.delete_link`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:452`

### `toggle_link`
- **Vollpfad:** `diakronos.diakonos.api.registrierungslink_api.toggle_link`
- Aufruf: `frontend/src/diakonos/pages/Registrierung.vue:439`

## `diakronos.diakonos.api.ressourcen`

### `create_buchung`
- **Vollpfad:** `diakronos.diakonos.api.ressourcen.create_buchung`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:664`

### `delete_buchung`
- **Vollpfad:** `diakronos.diakonos.api.ressourcen.delete_buchung`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:689`

### `get_anfragen`
- **Vollpfad:** `diakronos.diakonos.api.ressourcen.get_anfragen`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:471`

### `get_meine_buchungen`
- **Vollpfad:** `diakronos.diakonos.api.ressourcen.get_meine_buchungen`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:428`

### `get_ressourcen_liste`
- **Vollpfad:** `diakronos.diakonos.api.ressourcen.get_ressourcen_liste`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:418`

### `update_buchung`
- **Vollpfad:** `diakronos.diakonos.api.ressourcen.update_buchung`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:656`

## `diakronos.diakonos.api.session`

### `get_current_user_context`
- **Vollpfad:** `diakronos.diakonos.api.session.get_current_user_context`
- Aufruf: `frontend/src/diakonos/pages/Dsgvo.vue:70`

## `diakronos.diakonos.api.wiki`

### `create_wiki_artikel`
- **Vollpfad:** `diakronos.diakonos.api.wiki.create_wiki_artikel`
- Aufruf: `frontend/src/diakonos/pages/Wiki.vue:290`

### `delete_wiki_artikel`
- **Vollpfad:** `diakronos.diakonos.api.wiki.delete_wiki_artikel`
- Aufruf: `frontend/src/diakonos/pages/Wiki.vue:310`

### `get_wiki_artikel_detail`
- **Vollpfad:** `diakronos.diakonos.api.wiki.get_wiki_artikel_detail`
- Aufruf: `frontend/src/diakonos/pages/Wiki.vue:266`

### `get_wiki_artikel_liste`
- **Vollpfad:** `diakronos.diakonos.api.wiki.get_wiki_artikel_liste`
- Aufruf: `frontend/src/diakonos/pages/Wiki.vue:259`

### `update_wiki_artikel`
- **Vollpfad:** `diakronos.diakonos.api.wiki.update_wiki_artikel`
- Aufruf: `frontend/src/diakonos/pages/Wiki.vue:276`

## `diakronos.diakronos.api.ressourcen`

### `decide_buchung`
- **Vollpfad:** `diakronos.diakronos.api.ressourcen.decide_buchung`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:482`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:502`

## `diakronos.kronos.api.permissions`

### `get_session_info`
- **Vollpfad:** `diakronos.kronos.api.permissions.get_session_info`
- Aufruf: `frontend/src/diakonos/pages/Moderation.vue:111`
- Aufruf: `frontend/src/diakonos/pages/Ressourcen.vue:454`

## `diakronos.kronos.api.ressource_api`

### `get_ressources`
- **Vollpfad:** `diakronos.kronos.api.ressource_api.get_ressources`
- Aufruf: `frontend/src/diakonos/api/kanbanApi.js:79`

## `diakronos.kronos.api.series`

### `delete_series_batch_fast`
- **Vollpfad:** `diakronos.kronos.api.series.delete_series_batch_fast`
- Aufruf: `frontend/src/diakonos/api/kanbanApi.js:99`

### `update_series_batch_fast`
- **Vollpfad:** `diakronos.kronos.api.series.update_series_batch_fast`
- Aufruf: `frontend/src/diakonos/api/kanbanApi.js:88`

## `diakronos.psalmos.api.musik`

### `get_lied_detail`
- **Vollpfad:** `diakronos.psalmos.api.musik.get_lied_detail`
- Aufruf: `frontend/src/diakonos/pages/Lieder.vue:195`
- Aufruf: `frontend/src/diakonos/pages/LiedDetail.vue:231`

### `get_lieder`
- **Vollpfad:** `diakronos.psalmos.api.musik.get_lieder`
- Aufruf: `frontend/src/diakonos/pages/Lieder.vue:189`
- Aufruf: `frontend/src/diakonos/pages/Lieder.vue:246`
- Aufruf: `frontend/src/diakonos/pages/Lieder.vue:271`

### `get_liedgruppe_detail`
- **Vollpfad:** `diakronos.psalmos.api.musik.get_liedgruppe_detail`
- Aufruf: `frontend/src/diakonos/pages/LiedgruppeDetail.vue:172`

### `get_liedgruppen`
- **Vollpfad:** `diakronos.psalmos.api.musik.get_liedgruppen`
- Aufruf: `frontend/src/diakonos/pages/Liedgruppen.vue:105`
- Aufruf: `frontend/src/diakonos/pages/Lieder.vue:177`

---
## Nicht-`apiCall`-Aufrufe (weitere Quellen)

Diese Endpunkte werden ohne den `apiCall`-Helper aufgerufen und sind
zusaetzlich zu portieren:

- `diakronos.diakonos.api.audit.get_unread_notifications` — frontend/src/diakonos/composables/useNotifications.js:11 (apiGet)
- `diakronos.diakonos.api.dashboard.get_widget_data` — frontend/src/diakonos/composables/useWidgetData.js (direkter fetch, POST auf API_BASE)
- `diakronos.diakonos.api.dashboard.get_events_for_month` — frontend/src/diakonos/components/widgets/MiniCalendarWidget.vue
- `diakronos.diakonos.api.dashboard.get_widget_badge_counts` — frontend/src/diakonos/components/widgets/*
- `diakronos.diakonos.api.orgchart_api.get_orgchart_data` — frontend/src/diakonos (Organigramm-Widget)
- `diakronos.diakonos.api.registrierung.submit_registrierung` — frontend/src/registrierung/ (eigener Entry)
- `diakronos.diakonos.api.registrierung.submit_gast` — frontend/src/gast/ (eigener Entry)
- `diakronos.kronos.api.calendar_get.get_calendar_events` — frontend/src/diakonos/api/kanbanApi.js
- `upload_file` — frontend/src/** (Datei-Uploads, z.B. Mitgliederfoto/Logo)

---
## Hinweise fuer die Portierung

- **Namensraum `diakronos.diakonos.api.*`** ist der groesste Block (SPA-eigene
  Endpunkte: admin_hub, beitraege, gruppen, mitglieder, planung, ressourcen,
  wiki, registrierungslink_api, auswahl, dienstplan, session).
- **`diakronos.kronos.api.*`** (Kanban/Kalender) und **`diakronos.psalmos.api.musik.*`**
  (Lieder) stammen aus Fremd-Apps und werden mitportiert.
- Beim Umbau auf das neue Backend muss `apiCall` **eine** Stelle bleiben
  (`useApi.js`) — alle 78 Methoden laufen dort durch. Die Portierung ist
  damit ein reines Backend-Thema, solange der Pfad `/api/method/<method>`
  und die Frappe-Antwortkonvention beibehalten werden.
