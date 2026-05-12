import os
import json
import frappe


def get_frontend_assets(entry_name):
    manifest_path = frappe.get_app_path(
        "diakronos", "public", "frontend", ".vite", "manifest.json"
    )
    if not os.path.exists(manifest_path):
        return f"{entry_name}.js", []

    with open(manifest_path) as f:
        manifest = json.load(f)

    entry = next(
        (v for k, v in manifest.items() if v.get("isEntry") and entry_name in k),
        None,
    )
    if not entry:
        return f"{entry_name}.js", []

    js_file = entry.get("file", f"{entry_name}.js")
    css_files = []
    style_entry = manifest.get("style.css")
    if style_entry:
        css_files.append(style_entry.get("file"))
    css_files.extend(entry.get("css") or [])

    return js_file, css_files
