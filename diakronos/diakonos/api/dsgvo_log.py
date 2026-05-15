import frappe


def log_einwilligung(mitglied, typ, aktion, quelle="selfservice"):
    """Erzeugt einen unveränderlichen DSGVO-Einwilligung-Log-Eintrag.

    Schluckt Exceptions damit Log-Fehler den primären Save nicht blockieren.
    """
    try:
        ip = ""
        ua = ""
        if hasattr(frappe.local, "request") and frappe.local.request:
            ip = frappe.local.request.environ.get("REMOTE_ADDR") or ""
            ua = (frappe.local.request.headers.get("User-Agent") or "")[:200]

        # Letztes Oktett anonymisieren (IPv4)
        if ip:
            parts = ip.split(".")
            if len(parts) == 4:
                parts[3] = "0"
                ip = ".".join(parts)

        doc = frappe.get_doc({
            "doctype": "DSGVO Einwilligung",
            "mitglied": mitglied,
            "typ": typ,
            "aktion": aktion,
            "zeitstempel": frappe.utils.now_datetime(),
            "ip_adresse": ip,
            "user_agent": ua,
            "quelle": quelle,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Einwilligung Log Fehler")
