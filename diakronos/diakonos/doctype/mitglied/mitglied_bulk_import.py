# -*- coding: utf-8 -*-
# Copyright (c) 2025, [Dein Name] and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr, getdate, validate_email_address
from frappe.utils.csvutils import read_csv_content
import pandas as pd
import os
from typing import Dict, List, Any

@frappe.whitelist()
def mitglied_validate_import(file_url: str) -> Dict[str, Any]:
    """
    Validiert die Import-Datei vor dem eigentlichen Import
    
    Args:
        file_url: URL der hochgeladenen Datei
        
    Returns:
        Dictionary mit Validierungsergebnissen
    """
    try:
        # Datei laden
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_path = file_doc.get_full_path()
        
        # Dateityp erkennen und einlesen
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, encoding='utf-8')
        elif file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            frappe.throw(_("Nur CSV und Excel-Dateien (.csv, .xlsx, .xls) werden unterstützt"))
        
        # Pflichtfelder definieren
        required_fields = ["vorname", "nachname", "e_mail"]
        
        # Header normalisieren (zu lowercase und spaces ersetzen)
        df.columns = [col.lower().replace(" ", "_").replace("-", "_") for col in df.columns]
        
        # Prüfe ob Pflichtfelder vorhanden sind
        missing_fields = [f for f in required_fields if f not in df.columns]
        if missing_fields:
            frappe.throw(
                _("Fehlende Pflichtfelder: {0}").format(", ".join(missing_fields)),
                title=_("Validierungsfehler")
            )
        
        # Validierung durchführen
        validation_errors = []
        preview_data = []
        duplicate_count = 0
        
        for idx, row in df.iterrows():
            row_errors = []
            row_num = idx + 2  # +2 wegen Header und 0-basiertem Index
            
            # Validiere Pflichtfelder
            if pd.isna(row.get("vorname")) or not str(row.get("vorname")).strip():
                row_errors.append("Vorname fehlt")
            
            if pd.isna(row.get("nachname")) or not str(row.get("nachname")).strip():
                row_errors.append("Nachname fehlt")
            
            email = row.get("e_mail")
            if pd.isna(email) or not str(email).strip():
                row_errors.append("E-Mail fehlt")
            elif not validate_email_address(str(email).strip()):
                row_errors.append(f"Ungültige E-Mail-Adresse: {email}")
            
            # Duplikatsprüfung
            if not pd.isna(email):
                existing = frappe.db.exists("Mitglied", {"e_mail": str(email).strip()})
                if existing:
                    duplicate_count += 1
                    row_errors.append(f"Mitglied mit E-Mail {email} existiert bereits")
            
            # Datumsvalidierung
            if not pd.isna(row.get("geburtsdatum")):
                try:
                    getdate(row.get("geburtsdatum"))
                except:
                    row_errors.append("Ungültiges Geburtsdatum-Format (verwende YYYY-MM-DD)")
            
            if not pd.isna(row.get("mitglied_seit")):
                try:
                    getdate(row.get("mitglied_seit"))
                except:
                    row_errors.append("Ungültiges Format für 'Mitglied seit' (verwende YYYY-MM-DD)")
            
            # Fehler speichern
            if row_errors:
                validation_errors.append({
                    "row": row_num,
                    "errors": row_errors,
                    "data": row.to_dict()
                })
            
            # Preview-Daten (erste 10 Zeilen)
            if idx < 10:
                preview_data.append({
                    "row": row_num,
                    "vorname": row.get("vorname"),
                    "nachname": row.get("nachname"),
                    "e_mail": row.get("e_mail"),
                    "status": "Fehler" if row_errors else "OK",
                    "errors": ", ".join(row_errors) if row_errors else ""
                })
        
        return {
            "success": len(validation_errors) == 0,
            "total_rows": len(df),
            "valid_rows": len(df) - len(validation_errors),
            "error_count": len(validation_errors),
            "duplicate_count": duplicate_count,
            "errors": validation_errors[:50],  # Maximal 50 Fehler anzeigen
            "preview": preview_data,
            "message": _("Validierung erfolgreich") if len(validation_errors) == 0 else _("Validierung mit Fehlern")
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Import Validierung Fehler"))
        frappe.throw(
            _("Fehler beim Validieren der Datei: {0}").format(str(e)),
            title=_("Validierungsfehler")
        )


@frappe.whitelist()
def mitglied_bulk_import(file_url: str, create_users: int = 0) -> Dict[str, Any]:
    """
    Führt den Bulk-Import von Mitgliedern durch
    
    Args:
        file_url: URL der hochgeladenen Datei
        create_users: 1 wenn Benutzer automatisch angelegt werden sollen
        
    Returns:
        Dictionary mit Import-Ergebnissen
    """
    try:
        # Datei laden
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_path = file_doc.get_full_path()
        
        # Dateityp erkennen und einlesen
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, encoding='utf-8')
        elif file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            frappe.throw(_("Nur CSV und Excel-Dateien werden unterstützt"))
        
        # Header normalisieren
        df.columns = [col.lower().replace(" ", "_").replace("-", "_") for col in df.columns]
        
        success_count = 0
        error_list = []
        created_members = []
        
        # Import durchführen
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                # Prüfen ob Mitglied bereits existiert
                email = cstr(row.get("e_mail", "")).strip()
                existing = frappe.db.exists("Mitglied", {"e_mail": email})
                
                if existing:
                    error_list.append({
                        "row": row_num,
                        "error": f"Mitglied mit E-Mail {email} existiert bereits",
                        "vorname": row.get("vorname"),
                        "nachname": row.get("nachname")
                    })
                    continue
                
                # Neues Mitglied erstellen
                mitglied = frappe.new_doc("Mitglied")
                
                # Pflichtfelder
                mitglied.vorname = cstr(row.get("vorname", "")).strip()
                mitglied.nachname = cstr(row.get("nachname", "")).strip()
                mitglied.e_mail = email
                
                # Optionale Felder
                if not pd.isna(row.get("geburtsdatum")):
                    mitglied.geburtsdatum = getdate(row.get("geburtsdatum"))
                
                mitglied.postleitzahl = cstr(row.get("postleitzahl", ""))
                mitglied.strasse = cstr(row.get("strasse", ""))
                mitglied.wohnort = cstr(row.get("wohnort", ""))
                mitglied.nummer = cstr(row.get("nummer", ""))
                mitglied.telefonnummer = cstr(row.get("telefonnummer", ""))
                
                if not pd.isna(row.get("mitglied_seit")):
                    mitglied.mitglied_seit = getdate(row.get("mitglied_seit"))
                
                # Checkbox-Felder
                mitglied.auf_bemerkung_gesetzt = 1 if row.get("auf_bemerkung_gesetzt") in [1, "1", "Yes", "Ja", True] else 0
                
                # Flags setzen
                mitglied.flags.ignore_permissions = True
                mitglied.flags.ignore_mandatory = False
                
                # Speichern
                mitglied.insert()
                
                # Optional: Benutzer anlegen
                if create_users == 1 or create_users == "1":
                    try:
                        user_name = member_create_user(mitglied.name)
                        if user_name:
                            mitglied.benutzer = user_name
                            mitglied.save(ignore_permissions=True)
                    except Exception as e:
                        # Fehler beim Benutzer-Anlegen nicht als kritisch behandeln
                        frappe.log_error(
                            f"Benutzer konnte nicht angelegt werden für {mitglied.name}: {str(e)}",
                            _("Benutzer-Erstellung Fehler")
                        )
                
                success_count += 1
                created_members.append({
                    "name": mitglied.name,
                    "vorname": mitglied.vorname,
                    "nachname": mitglied.nachname,
                    "e_mail": mitglied.e_mail
                })
                
            except Exception as e:
                error_list.append({
                    "row": row_num,
                    "error": str(e),
                    "vorname": row.get("vorname"),
                    "nachname": row.get("nachname")
                })
                frappe.log_error(
                    f"Import Error Row {row_num}: {frappe.get_traceback()}",
                    _("Mitglied Import Fehler")
                )
        
        # Commit der Transaktion
        frappe.db.commit()
        
        return {
            "success": success_count,
            "errors": error_list,
            "total": len(df),
            "created_members": created_members[:10],  # Erste 10 zur Anzeige
            "message": _("{0} von {1} Mitgliedern erfolgreich importiert").format(success_count, len(df))
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), _("Bulk Import Fehler"))
        frappe.throw(
            _("Fehler beim Importieren: {0}").format(str(e)),
            title=_("Import Fehler")
        )


def member_create_user(mitglied_name: str) -> str:
    """
    Erstellt einen Benutzer aus Mitglied-Daten
    
    Args:
        mitglied_name: Name des Mitglied-Dokuments
        
    Returns:
        Name des erstellten Benutzers
    """
    mitglied = frappe.get_doc("Mitglied", mitglied_name)
    
    if not mitglied.e_mail:
        frappe.throw(_("E-Mail ist erforderlich um einen Benutzer anzulegen"))
    
    # Prüfen ob User bereits existiert
    if frappe.db.exists("User", mitglied.e_mail):
        return mitglied.e_mail
    
    user = frappe.new_doc("User")
    user.email = mitglied.e_mail
    user.first_name = mitglied.vorname
    user.last_name = mitglied.nachname
    user.send_welcome_email = 0
    user.enabled = 1
    
    # Standard-Rolle zuweisen (anpassen nach Bedarf)
    user.append("roles", {
        "role": "Mitglied"  # Stelle sicher dass diese Rolle existiert
    })
    
    user.insert(ignore_permissions=True)
    
    return user.name


@frappe.whitelist()
def mitglied_download_template() -> str:
    """
    Generiert und lädt ein Import-Template herunter
    
    Returns:
        CSV-String mit Template
    """
    import io
    
    # Template-Daten
    headers = [
        "vorname",
        "nachname", 
        "e_mail",
        "geburtsdatum",
        "postleitzahl",
        "strasse",
        "wohnort",
        "nummer",
        "telefonnummer",
        "mitglied_seit",
        "auf_bemerkung_gesetzt"
    ]
    
    example_data = [
        ["Max", "Mustermann", "max@example.com", "1990-01-15", "74861", "Talstraße", "Siglingen", "29", "0123456789", "2015-03-05", "0"],
        ["Maria", "Musterfrau", "maria@example.com", "1985-07-22", "12345", "Beispielweg", "Beispielort", "5", "9876543210", "2018-06-12", "1"]
    ]
    
    # CSV erstellen
    output = io.StringIO()
    import csv
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(example_data)
    
    return output.getvalue()
