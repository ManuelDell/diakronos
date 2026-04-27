# Zusammenfassung: Audit & Policy Enforcement Layer (Frontend)

## Erstellte Dateien

| Datei | Beschreibung |
|-------|-------------|
| `composables/useAuditConfirm.js` | Globales Singleton-Composable für das Audit-Bestätigungs-Modal. Exportiert `isOpen`, `currentPolicy`, `openConfirm()`, `submit()`, `cancel()`. `openConfirm()` gibt ein Promise zurück, das mit der Begründung resolved oder mit `null` bei Abbruch. |
| `components/DkModal.vue` | Wiederverwendbare Modal-Komponente basierend auf dem bestehenden `dk-modal-overlay`/`dk-modal` CSS-Pattern. Nutzt `<Teleport to="body">`. |
| `components/AuditConfirmModal.vue` | Globales Singleton-Modal für Audit-Bestätigungen. Nutzt `DkModal`, `useAuditConfirm` und die bestehenden `dk-*` Formular-Klassen. |
| `composables/useNotifications.js` | Singleton-Composable für Notification-Polling. Startet beim Mount ein 60-Sekunden-Intervall auf `diakronos.diakonos.api.audit.get_unread_notifications`. Bietet `markAsRead()` per API-Call. |

## Geänderte Dateien

| Datei | Änderungen |
|-------|-----------|
| `composables/useApi.js` | Neue Fehlerklasse `AuditConfirmationRequired extends Error` mit `policy`-Property hinzugefügt. `apiCall()` prüft jetzt auf `message.requires_confirmation === true` und wirft statt eines generischen Fehlers eine `AuditConfirmationRequired`. Keine Rekursion. |
| `App.vue` | `<AuditConfirmModal />` app-weit einmalig im Layout gerendert. |
| `pages/MitgliedDetail.vue` | `saveEdit()` fängt `AuditConfirmationRequired` ab, öffnet das Modal via `useAuditConfirm`, und sendet bei Bestätigung einen neuen Request mit `__audit_confirmation`-Payload inkl. `idempotency_key`. `canEdit` nutzt jetzt `isAdmin` statt `isAdminMode`. Admin-Mode-Badge entfernt. |
| `components/AppTopbar.vue` | Admin-Mode-Indikator komplett entfernt. Notification-Glocke zeigt jetzt einen Badge-Zähler (`dk-notify-badge`) und ruft bei Klick `markAsRead()` auf. |
| `index.css` | Neue Utility-Klasse `.dk-notify-badge` für den Notification-Zähler neben der Glocke hinzugefügt (nutzt `var(--dk-danger)`). |

## Architektur-Highlights

- **Keine Rekursion in `apiCall`:** Die aufrufende Komponente (hier `MitgliedDetail.vue`) handhabt den Retry mit Bestätigungspayload selbst.
- **Globales Singleton:** `AuditConfirmModal` wird einmal in `App.vue` gerendert. `useAuditConfirm` und `useNotifications` arbeiten mit modul-level State, sodass nur eine Modal-Instanz und ein Polling-Intervall existieren.
- **Idempotency-Key:** `generateIdempotencyKey()` verwendet `crypto.randomUUID()` mit Fallback auf Timestamp+Random.
- **Design-System:** Alle neuen Komponenten nutzen ausschließlich bestehende `dk-*` CSS-Klassen (keine hartcodierten Farben/Größen).
