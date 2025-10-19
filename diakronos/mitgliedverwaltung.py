import frappe
import json

@frappe.whitelist()
def mitglied_zu_nutzer(doc=None):
    if doc is None:
        return "Kein Mitglied-Dokument übergeben."
    # doc ist ein JSON-String → umwandeln!
    if isinstance(doc, str):
        doc = json.loads(doc)
    mitglied = doc.get("name")
    email = doc.get("email")
    vorname = doc.get("vorname")
    nachname = doc.get("nachname")

    if not (email and vorname and nachname):
        return "Fehlende Felder: bitte alle Daten angeben!"
    if frappe.db.exists("User", email):
        return f"Ein Benutzer mit der E-Mail {email} existiert bereits."
    user = frappe.new_doc("User")
    user.email = email
    user.first_name = vorname
    user.last_name = nachname
    user.enabled = 1
    user.insert(ignore_permissions=True)
    user.append("roles", {"role": "Mitglied"})
    user.save(ignore_permissions=True)
    frappe.db.set_value("Mitglied", mitglied, "user", user.name)
    # Passwort-Mail: Siehe Frappe 16+ Hinweise; ggf. eigenen Workflow nutzen!
    return f"Benutzer {user.name} angelegt."
