# AGENTS.md — Diakronos DSGVO-Compliance

**Dieses Dokument ist bindend für alle KI-Agenten und Entwickler, die an diesem Codebase arbeiten.**

---

## 1. Grundsatz

Diakronos verarbeitet personenbezogene Daten von Vereinsmitgliedern nach DSGVO.
Jede Einwilligung (Datenschutzerklärung, Foto, Werbung) muss:

- **nachweisbar** sein (Art. 7 Abs. 1 DSGVO)
- **unveränderlich geloggt** werden (Art. 5 Abs. 2 DSGVO — Rechenschaftspflicht)
- **nach Datenlöschung erhalten bleiben** (Art. 17 Abs. 3 lit. b DSGVO — Logs überleben den Account)

---

## 2. Einwilligungs-Felder im DocType `Mitglied`

| Feldname | Typ | Bedeutung |
|---|---|---|
| `datenschutz_einwilligung` | Check | Allgemeine Datenschutzerklärung |
| `datenschutz_datum` | Date | Datum der Zustimmung |
| `foto_einwilligung` | Check | Einwilligung zur Foto-/Bildveröffentlichung |
| `foto_datum` | Date | Datum der Foto-Einwilligung |
| `werbeeinwilligung` | Check | Einwilligung zu Werbezwecken |
| `werbung_datum` | Date | Datum der Werbeeinwilligung |

**Alle sechs Felder sind `read_only: 1` im DocType-JSON** — sie dürfen NUR über whitelisted API-Funktionen geändert werden, niemals direkt über die Frappe-UI oder rohe DB-Updates ohne Logging.

---

## 3. Pflicht-Logging — Einwilligung Log

**TODO: DocType `Einwilligung Log` (Phase 1 — noch zu implementieren)**

Jede Änderung an Einwilligungs-Feldern MUSS einen unveränderlichen Log-Eintrag erzeugen mit:

```
- mitglied: Link zu Mitglied (Name/ID)
- typ: "datenschutz" | "foto" | "werbung"
- aktion: "erteilt" | "widerrufen"
- datum: datetime (UTC)
- ip_adresse: Request-IP (anonymisiert: letztes Oktett = 0)
- user_agent: Browser-String (gekürzt auf max 200 Zeichen)
- quelle: "selfservice" | "admin" | "import" | "api"
- unveraenderlich: 1 (kein Delete, kein Amend erlaubt)
```

**Implementierungs-Regeln:**
- DocType: `submit`-fähig, kein `is_submittable` nötig — stattdessen: kein Delete-Permission für niemanden
- `on_trash`-Hook im DocType: `frappe.throw("Einwilligung-Logs dürfen nicht gelöscht werden")`
- Log-Einträge überleben Anonymisierung (referenzieren `mitglied.name`, nicht die PII)

---

## 4. Hook-Punkte — Wo muss geloggt werden?

| Funktion | Datei | Typ | Pflicht |
|---|---|---|---|
| `update_einwilligung(typ="foto")` | `api/profile.py` | foto / werbung | ✅ |
| `update_einwilligung(typ="werbung")` | `api/profile.py` | foto / werbung | ✅ |
| `widerruf_einwilligung()` | `api/mitglieder.py` | alle | ✅ |
| `delete_my_data()` | `api/profile.py` | alle (Widerruf) | ✅ |
| Initiale Registrierung | (zukünftig) | datenschutz | ✅ |
| Admin-seitige Änderung | Frappe DocType Hook | alle | ✅ |

---

## 5. Anonymisierung bei Datenlöschung (`delete_my_data`)

Wenn ein Mitglied seine Daten löscht (Art. 17 DSGVO):

1. PII-Felder werden überschrieben (Vorname="Gelöscht", Email=deleted-{name}@deleted.invalid, etc.)
2. Alle Einwilligungs-Felder werden auf `0` / `None` gesetzt
3. **Log-Einträge bleiben erhalten** — sie referenzieren nur `mitglied.name` (technische ID), nicht PII
4. Der Frappe-User-Account wird deaktiviert

---

## 6. Regeln für KI-Agenten

### ❌ VERBOTEN — niemals tun:
- Einwilligungs-Felder direkt via `doc.field = value; doc.save()` ändern ohne `_log_einwilligung()` aufzurufen
- Log-Einträge löschen, archivieren oder modifizieren
- Die `on_trash`-Sperre im `Einwilligung Log` DocType entfernen oder umgehen
- `frappe.db.sql("UPDATE tabMitglied SET foto_einwilligung=...")` ohne Log
- `ignore_permissions=True` bei Einwilligungs-Änderungen ohne gleichzeitigen Log-Eintrag

### ✅ ERLAUBT — so sollen Einwilligungen geändert werden:
```python
# Korrekt: frappe.db.set_value() + _log_einwilligung()
frappe.db.set_value("Mitglied", mid, {"foto_einwilligung": 1, "foto_datum": heute})
_log_einwilligung(mid, "foto", "erteilt", quelle="selfservice")
frappe.db.commit()
```

### ⚠️ WARNUNG — Audit Policy:
`doc.save(ignore_permissions=True)` auf dem DocType `Mitglied` kann durch die Frappe Audit Policy (`CONFIRM_REQUIRED`) abgebrochen werden — der Save schlägt dann lautlos fehl. Daher: für Einwilligungs-Felder immer `frappe.db.set_value()` verwenden.

---

## 7. Geplante Implementierungs-Phasen

| Phase | Was | Status |
|---|---|---|
| Phase 1 | `Einwilligung Log` DocType anlegen | ✅ Implementiert |
| Phase 2 | `log_einwilligung()` Helper in `api/dsgvo_log.py` | ✅ Implementiert |
| Phase 3 | Alle Hook-Punkte verdrahten | ✅ Implementiert |
| Phase 4 | Immutability via `before_save` + `on_trash` | ✅ Implementiert |
| Phase 5 | Anonymisierung bei `delete_my_data` verifizieren | ✅ Implementiert |

---

## 8. Verantwortlichkeit

Der technisch Verantwortliche nach Art. 24 DSGVO für dieses System ist der Betreiber der Diakronos-Instanz.
Dieses Dokument ist Teil der technischen und organisatorischen Maßnahmen (TOM) nach Art. 32 DSGVO.

Letzte Aktualisierung: 2026-05-15
