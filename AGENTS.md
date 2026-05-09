# Diakronos — AGENTS.md

Self-hosted church management (Frappe + Vue 3 + MariaDB). MIT, Dells Dienste.  
**App path:** `/home/erpnext/frappe-bench/apps/diakronos/`  
**Branch:** `develop` (active), `v16` (local dev base)  
**Build:** `cd apps/diakronos && yarn build` → `diakronos/public/frontend/`  
**Bench root:** `/home/erpnext/frappe-bench`  
**Dev SSH host:** `lokal-Frappe-Development`

---

## Stack & Build

- Backend: Frappe (Python), whitelisted methods via `hooks.py`
- Frontend: Vue 3 SPA (Vite), hash-based routing, `--dk-*` CSS design system
- DB: MariaDB via Frappe ORM
- **`bench build` does NOT compile Vue** — always `yarn build` in app root
- Built JS is **tracked in git** (`public/frontend/` not gitignored)
- After DocType/Python changes: `bench migrate` + `bench restart`

---

## Python Module Map

| Dir | Role | Notes |
|---|---|---|
| `diakronos/diakronos/` | Core: settings, auth, fixtures | App config — not member module |
| `diakronos/diakonos/` | Member management module | **Different from `diakronos/`** |
| `diakronos/kronos/` | Calendar & events | `Element` = main event DocType |
| `diakronos/psalmos/` | Song management | Stub only, no active code |
| `diakronos/seelsorge/` | Pastoral care | Stub only, no active code |
| `diakronos/caldav/` | Read-only CalDAV server | Intercepts `/dav/*` via `before_request` |

---

## DocTypes

**Diakonos** (`diakonos/doctype/`):  
`anmeldeformular`, `anmeldeformular_dokument`, `anmeldeformular_feld`, `anmeldung`, `anmeldung_antwort`, `anmeldung_kind`, `audit_log`, `audit_policy`, `beitrag`, `beitrag_kommentar`, `dienstbereich`, `dienstbereich_verantwortlicher` *(child: `user` → Frappe User)*, `dienstrolle`, `dsgvo_einwilligung`, `gruppe`, `gruppe_verantwortlicher` *(child: `verantwortlicher` → Mitglied)*, `gruppenmitgliedschaft`, `gruppenrolle`, `gruppentyp`, `mitglied`, `mitglied_bereich`, `mitglied_beziehung`, `mitglied_tag`, `registrierungslink`, `ressourcen_buchung`, `sicherer_anhang`, `untergruppe`, `untergruppe_verantwortlicher`, `untergruppenmitgliedschaft`, `user_notification_preference`, `wiki_artikel`

**Kronos** (`kronos/doctype/`):  
`ablaufplan`, `ablaufplan_position`, `element`, `element_mitarbeiter`, `eventkategorie`, `google_kalender_einstellungen`, `kalender`, `kalender_moderator`, `kronos_einstellungen`, `kronos_kanban_zustand`, `ressource`

---

## API Layer

**Rule:** Every public endpoint must be in `hooks.py → whitelisted_methods` (else 403).

**Diakonos API** (`diakonos/api/`):

| File | Responsibility |
|---|---|
| `admin_hub.py` | Stats, Anmeldungen, DSGVO overview, approval flows |
| `audit.py` | Audit log read |
| `audit_policy/` | DSGVO anonymisation policy |
| `beitraege.py` | Posts + comments CRUD |
| `cleanup.py` | Daily cleanup scheduler (old Anmeldeanfragen) |
| `dienstplan.py` | Service roster (backend TODO — stubs in Home.vue) |
| `dsgvo_export.py` | DSGVO data export |
| `gruppen.py` | Group hierarchy, create Dienstbereich/Gruppe/Untergruppe, permissions |
| `kalender.py` | SPA calendar events |
| `mitglieder.py` | Member CRUD, list |
| `nutzer.py` | User account ops |
| `orgchart_api.py` | Org-chart data |
| `registrierung.py` | Public registration flow |
| `registrierungslink_api.py` | Registration link CRUD |
| `ressourcen.py` | Resource booking CRUD |
| `session.py` | `check_permission(doctype, name, perm)` |
| `veranstaltungsanmeldung.py` | One-click event registration |
| `wiki.py` | Wiki CRUD |
| `zugriff.py` | `verify_admin_session()` for elevated ops |

**Kronos API** (`kronos/api/`):

| File | Responsibility |
|---|---|
| `calendar_get.py` | Main calendar events feed |
| `event_crud.py` | Element create/update/delete |
| `google_import.py` | Google Calendar OAuth + import |
| `kanban_api.py` | Kanban board state |
| `permissions.py` | Module access, home preference |
| `ressource_api.py` | Room/resource calendar |
| `search_api.py` | Awesome Bar event search |
| `series.py` | Recurring event series logic |

---

## Frontend (Vue 3 SPA)

**Source:** `frontend/src/diakonos/`

**Pages:** `Home`, `Mitglieder`, `MitgliedDetail`, `Gruppen`, `GruppeDetail`, `Adressbuch`, `Kalender`, `Dienstplan`, `Organigramm`, `Statistik`, `Dsgvo`, `Profile`, `Ressourcen`, `Beitraege`, `Wiki`, `Registrierung`

**Components:** `AppSidebar`, `AppTopbar`, `AuditConfirmModal`, `DkModal`, `GruppenItem`

**Composables:**

| File | Purpose |
|---|---|
| `useApi.js` | `apiCall(method, args)` → `frappe.call` wrapper |
| `useSession.js` | Current user / mitglied / isAdmin |
| `useMitglieder.js` | Shared member list/cache |
| `useNotifications.js` | In-app notifications |
| `useToast.js` | Toast messages |
| `useAuditConfirm.js` | Audit confirmation modal trigger |

**Routing (hash-based):**
- Exact: `#/` `#/mitglieder` `#/gruppen` `#/kalender` etc.
- Dynamic: `#/mitglied/:id` → `MitgliedDetail`, `#/gruppe/:id` → `GruppeDetail`
- Guards: Gast-status → locked to `#/` `#/kalender` `#/profile`

**WWW routes:**

| Path | Handler |
|---|---|
| `/diakonos/*` | Vue SPA (hash router takes over) |
| `/dav/*` | CalDAV (intercept in `before_request`) |
| `/registrierung` | Public registration SPA |
| `/gast` | Guest view SPA |
| `/kronos` | Kronos calendar page |

**CSS design system:** `--dk-surface`, `--dk-surface-2`, `--dk-text`, `--dk-text-muted`, `--dk-text-subtle`, `--dk-border`, `--dk-btn-primary`, `--dk-danger`, `--dk-primary`

**Modal pattern:** `<DkModal>` component or `<Teleport to="body">` + `.dk-modal-overlay > .dk-modal`

**Login redirect:** Admins → `/app` | Members → `/diakonos` (via `auth.py::get_home_page`)

---

## Permission Model

**Frappe Roles:** System Manager, Mitgliederadministrator, Gemeindeverantwortlicher, Kalenderadministrator, Psalmos-Nutzer, Mitglied

**Group hierarchy (top → bottom):**

```
Dienstbereich  ←  Dienstbereich Verantwortlicher.user (Frappe User)
  └── Gruppe   ←  Gruppe Verantwortlicher.verantwortlicher (→ Mitglied)
        └── Untergruppe  ←  Untergruppe Verantwortlicher.verantwortlicher (→ Mitglied)
```

**Creation rules (top-down only):**
- Gemeindeverantwortliche → create Dienstbereich
- Dienstbereichsverantwortliche → create Gruppe (in their Dienstbereich)
- Gruppenverantwortliche → create Untergruppe (in their Gruppe)

**`ancestor_path` field:** Precomputed hierarchy path on `Gruppe`, `Untergruppe`, `Mitglied` for efficient permission checks.

**Audit Log:** Immutable (`on_update`/`on_trash` → throw). Daily scheduler anonymises expired entries per `DsgvoEinwilligung` policy.

**Admin session:** `verify_admin_session()` in `zugriff.py` — required for admin-hub elevated ops, separate from Frappe role check.

---

## Open TODOs

| Area | Status |
|---|---|
| `Dienstplan` | Frontend stubs only (`get_meine_dienste`, `get_dienstanfragen`), no backend |
| `Kronos core/manager.py` | 3× `# TODO: Phase 2` — advanced series logic |
| `Psalmos` | Dir + www-page exists, no DocTypes/API |
| `Seelsorge` | Dir exists, no implementation |
| Raven chat | Planned integration (group → channel), commented out in hooks.py |

---

## Quick Reference

| Task | Command / Location |
|---|---|
| Build frontend | `cd /home/erpnext/frappe-bench/apps/diakronos && yarn build` |
| Start bench | `cd /home/erpnext/frappe-bench && bench start` |
| Migrate DB | `cd /home/erpnext/frappe-bench && bench migrate` |
| Restart workers | `cd /home/erpnext/frappe-bench && bench restart` |
| Add API endpoint | Implement in `diakonos/api/` → add to `hooks.py` `whitelisted_methods` |
| New DocType | Create JSON in `doctype/` dir → `bench migrate` |
| Frontend API call | `apiCall('diakronos.diakonos.api.module.function', {args})` |

---

## Critical Gotchas

1. `bench build` ≠ Vue build — use `yarn build` always
2. `diakronos/` (app config) ≠ `diakonos/` (member module) — easy typo, hard bug
3. New `@frappe.whitelist()` methods need manual entry in `hooks.py → whitelisted_methods`
4. CalDAV intercepts before Frappe routing — don't add `/dav/*` www routes
5. `public/frontend/` JS is git-tracked — commit after every build that changes behaviour
6. Frappe child tables: `doc.append(fieldname, {...})` + `doc.save()` — never direct DB insert
7. d3-org-chart v3 requires EXACTLY ONE root node (parentId: null). Multiple roots → `Error: multiple roots`. Always include one virtual root `{"id":"virtual-root","parentId":None,"type":"root"}`; render it invisibly with `nodeWidth(d => d.data.type==='root' ? 1 : 200)` etc.
