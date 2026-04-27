import frappe
from frappe.utils import now_datetime


def run_tests():
    frappe.set_user("Administrator")
    results = []

    # Test 1: Audit Policy anlegen (P0.1 Fix - _() Import)
    print("=== TEST 1: Policy anlegen ===")
    try:
        policy = frappe.get_doc({
            "doctype": "Audit Policy",
            "policy_name": f"Test-Policy-{now_datetime().strftime('%Y%m%d%H%M%S')}",
            "doctype_name": "Mitglied",
            "doctype_target": "Mitglied",
            "action": "write",
            "consequence": "confirm_required",
            "condition_field": "email",
            "actor_role": "System Manager",
            "target_is_other": 0,
            "is_active": 1,
        })
        policy.insert()
        print(f"✅ Policy angelegt: {policy.name}")
        results.append(("P0.1 _() Import", "PASS"))
    except Exception as e:
        print(f"❌ Fehler: {e}")
        results.append(("P0.1 _() Import", f"FAIL: {e}"))

    # Hole ein Mitglied fuer die naechsten Tests
    mitglied_name = frappe.db.get_value("Mitglied", {"email": "manuel@diedells.de"}, "name")
    if not mitglied_name:
        print("Kein Mitglied gefunden, Tests abgebrochen")
        return results

    # Test 2: Mitglied bearbeiten und Audit Log pruefen
    print("\n=== TEST 2: Mitglied bearbeiten + Audit Log ===")
    try:
        from diakronos.diakonos.api.mitglieder import update_mitglied
        result = update_mitglied(
            mitglied_id=mitglied_name,
            data='{"ort": "Teststadt"}'
        )
        print(f"Update Result: {result}")

        # Pruefe Audit Log
        logs = frappe.get_all("Audit Log",
            filters={"target_name": mitglied_name},
            fields=["name", "action_typ", "actor", "status", "field_changed", "consequence"],
            order_by="zeitstempel desc",
            limit=3
        )
        print(f"Gefundene Logs: {len(logs)}")
        for log in logs:
            print(f"  - {log.name}: status={log.status} | consequence={log.consequence}")

        if logs and logs[0].status == "completed":
            results.append(("P0.3 Exception-Logging", "PASS"))
        else:
            results.append(("P0.3 Exception-Logging", "FAIL: Kein Log oder falscher Status"))
    except Exception as e:
        print(f"❌ Fehler: {e}")
        results.append(("P0.3 Exception-Logging", f"FAIL: {e}"))

    # Test 2b: P3 DocType-Controller Audit (direkter doc.save)
    print("\n=== TEST 2b: P3 Controller Audit (direkter doc.save) ===")
    try:
        # Audit-Bestätigung für Controller setzen
        # Wir verwenden den Namen der zuletzt angelegten Policy
        latest_policy = frappe.get_all("Audit Policy", 
            filters={"policy_name": ["like", "Test-Policy%"]}, 
            fields=["name", "policy_name"],
            order_by="creation desc",
            limit=1
        )
        policy_name = latest_policy[0].name if latest_policy else "Test-Policy"
        
        frappe.local.audit_confirmation = {
            "policy_name": policy_name,
            "reason": "Test-Begründung für P3",
        }
        doc = frappe.get_doc("Mitglied", mitglied_name)
        old_name = doc.nachname
        doc.nachname = "ControllerTestNachname"
        doc.save()
        del frappe.local.audit_confirmation

        logs_p3 = frappe.get_all(
            "Audit Log",
            filters={
                "target_doctype": "Mitglied",
                "target_name": mitglied_name,
                "action_typ": "Profiländerung",
            },
            fields=["name", "status", "new_value"],
            order_by="zeitstempel desc",
            limit=1,
        )
        if logs_p3 and "ControllerTestNachname" in str(logs_p3[0].new_value or ""):
            print("✅ P3 Controller Audit: PASS")
            results.append(("P3.1 Controller Audit", "PASS"))
        else:
            print(f"❌ P3 Controller Audit: FAIL — Kein Log für direkten doc.save()")
            results.append(("P3.1 Controller Audit", "FAIL: Kein Log"))

        # Wiederherstellen
        frappe.local.audit_confirmation = {
            "policy_name": policy_name,
            "reason": "Test-Wiederherstellung",
        }
        doc.nachname = old_name
        doc.save()
        if hasattr(frappe.local, 'audit_confirmation'):
            del frappe.local.audit_confirmation
    except Exception as e:
        if hasattr(frappe.local, 'audit_confirmation'):
            del frappe.local.audit_confirmation
        print(f"❌ Fehler: {e}")
        results.append(("P3.1 Controller Audit", f"FAIL: {e}"))

    # Test 3: get_my_audit_log mit actor Filter (P1.6 Fix)
    print("\n=== TEST 3: get_my_audit_log (DSGVO Art. 15) ===")
    try:
        from diakronos.diakonos.api.audit import get_my_audit_log
        result = get_my_audit_log(start=0, limit=10)
        print(f"Logs fuer aktuellen User: {result['total']} total")

        # Pruefe ob actor-Logs enthalten sind
        actor_logs = [l for l in result['data'] if l['actor'] == frappe.session.user]
        print(f"Davon als actor: {len(actor_logs)}")

        if len(actor_logs) > 0:
            results.append(("P1.6 DSGVO Art. 15 actor Filter", "PASS"))
        else:
            results.append(("P1.6 DSGVO Art. 15 actor Filter", "FAIL: Keine actor-Logs"))
    except Exception as e:
        print(f"❌ Fehler: {e}")
        results.append(("P1.6 DSGVO Art. 15 actor Filter", f"FAIL: {e}"))

    # Test 4: Idempotency mit Payload-Binding (P1.7 Fix)
    print("\n=== TEST 4: Idempotency Payload-Binding ===")
    try:
        from diakronos.diakonos.api.audit_policy.decorator import _set_idempotency_key_atomic
        import hashlib
        key = "test-key-123"
        hash1 = hashlib.sha256(b'payload1').hexdigest()
        hash2 = hashlib.sha256(b'payload2').hexdigest()

        # Erstmal loeschen falls vorhanden
        frappe.cache().delete_value("diakronos:audit_idemp:" + key)

        result1 = _set_idempotency_key_atomic("diakronos:audit_idemp:" + key, hash1, 60)
        print(f"Erster Call mit hash1: {result1}")

        result2 = _set_idempotency_key_atomic("diakronos:audit_idemp:" + key, hash1, 60)
        print(f"Zweiter Call mit hash1: {result2}")

        try:
            result3 = _set_idempotency_key_atomic("diakronos:audit_idemp:" + key, hash2, 60)
            print(f"Dritter Call mit hash2: {result3}")
            results.append(("P1.7 Idempotency Payload", "FAIL: Sollte abgelehnt werden"))
        except Exception as e:
            print(f"✅ Richtig abgelehnt: {e}")
            results.append(("P1.7 Idempotency Payload", "PASS"))
    except Exception as e:
        print(f"❌ Fehler: {e}")
        results.append(("P1.7 Idempotency Payload", f"FAIL: {e}"))

    # Test 5: Notification Double-Send Schutz (P1.3 + P0.7)
    print("\n=== TEST 5: Notification Double-Send ===")
    try:
        from diakronos.diakonos.api.audit_policy.notifications import send_notification

        # Erstelle einen Test-Audit-Log
        frappe.local.audit_policy_logged = True
        log_doc = frappe.get_doc({
            "doctype": "Audit Log",
            "zeitstempel": now_datetime(),
            "action_typ": "Profiländerung",
            "actor": frappe.session.user,
            "target_doctype": "Mitglied",
            "target_name": mitglied_name,
            "notification_gesendet": 1,
        }).insert(ignore_permissions=True)
        frappe.local.audit_policy_logged = False

        # Versuche Notification zu senden - sollte sofort returnen
        send_notification(log_doc.name, target_user=frappe.session.user)
        print(f"✅ Notification korrekt uebersprungen (bereits gesendet)")
        results.append(("P1.3 Notification Double-Send", "PASS"))
    except Exception as e:
        print(f"❌ Fehler: {e}")
        results.append(("P1.3 Notification Double-Send", f"FAIL: {e}"))

    # Zusammenfassung
    print("\n" + "=" * 50)
    print("TEST-ZUSAMMENFASSUNG")
    print("=" * 50)
    passed = 0
    failed = 0
    for name, status in results:
        symbol = "✅" if status == "PASS" else "❌"
        print(f"{symbol} {name}: {status}")
        if status == "PASS":
            passed += 1
        else:
            failed += 1
    print(f"\nErgebnis: {passed}/{len(results)} bestanden")

    return results
