"""Plan-Rahmen — Sperre des generischen Resource-CRUD (ohne DB).

Diese Prüfungen laufen in der Standard-Suite (SQLite) und sichern ab, dass die
handgepflegten pr_*-Tabellen des Plan-Rahmens niemals über den generischen
Frappe-Resource-CRUD (`/api/resource/<doctype>`) erreichbar werden.

Zwei Verteidigungslinien (siehe `frappe_compat/router.py`):
  1. die pr_*-Namen stehen nicht in `models/_mapping.json` (registern nicht im
     generischen CRUD) und
  2. `_private_resource_denied` sperrt die DocType-Namen ausdrücklich — selbst
     wenn eine Tabelle je ins Mapping geriete.
"""

from __future__ import annotations


def test_planrahmen_doctypes_sind_im_resource_crud_gesperrt():
    """Jeder Plan-Rahmen-DocType ist im generischen Resource-CRUD gesperrt."""

    from diakronos_app.frappe_compat.router import _PLANRAHMEN_DOCTYPES, _private_resource_denied

    assert _PLANRAHMEN_DOCTYPES, "Sperrliste darf nicht leer sein"
    for doctype in _PLANRAHMEN_DOCTYPES:
        assert _private_resource_denied(doctype) is True, (
            f"DocType {doctype!r} ist nicht gesperrt"
        )


def test_planrahmen_tabellen_nicht_im_generischen_mapping():
    """Gegenprobe: die pr_*-Namen stehen nicht im generischen Mapping."""

    from diakronos_app.frappe_compat import registry_gen

    for doctype in (
        "Plantyp",
        "Plantyp Version",
        "Plan",
        "Termin",
        "Eintrag",
        "Verlauf",
        "Merkmal",
        "Merkmal Wert",
        "Sammlung",
        "Sammlung Eintrag",
        "Abwesenheit",
    ):
        assert registry_gen.is_known(doctype) is False, (
            f"{doctype!r} taucht im generischen Mapping auf — Plan-Rahmen-Tabellen "
            "dürfen nicht über den generischen Resource-CRUD erreichbar sein."
        )


def test_planrahmen_modelle_nicht_im_mapping_json():
    """Gegenprobe auf Datei-Ebene: kein pr_-Eintrag in models/_mapping.json."""

    import json
    from pathlib import Path

    mapping_path = (
        Path(__file__).resolve().parents[1]
        / "src" / "diakronos_app" / "models" / "_mapping.json"
    )
    if not mapping_path.is_file():  # pragma: no cover — Deployment-Kontext
        import pytest

        pytest.skip("_mapping.json nicht vorhanden (Deployment-Kontext)")

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    praefix_lecks = [
        table
        for entry in mapping.values()
        if (table := entry.get("table", "")).startswith("pr_")
    ]
    assert not praefix_lecks, (
        f"pr_-Tabellen im generischen Mapping: {praefix_lecks} — "
        "Plan-Rahmen-Modelle sind handgepflegt und gehören nicht dorthin."
    )


def test_planrahmen_resource_routen_antworten_403(client):
    """Die echten Resource-Routen antworten fuer pr_-DocTypes mit sauberem 403.

    Der direkte Test auf `_private_resource_denied` (oben) greift nicht, wo
    `resource_get` den deny-Fall an einen Mitglied-Sonderweg haengt — diese
    Pruefung faehrt die echten HTTP-Routen (Liste UND Einzelabruf) und verlangt
    fuer jede pr_-DocType ein 403 statt eines Mitglied-Detail-Durchreichens.
    """

    for doctype in (
        "Plantyp",
        "Plantyp Version",
        "Plan",
        "Termin",
        "Eintrag",
        "Verlauf",
        "Merkmal",
        "Merkmal Wert",
        "Sammlung",
        "Sammlung Eintrag",
        "Abwesenheit",
    ):
        liste = client.get(f"/api/resource/{doctype}")
        assert liste.status_code == 403, (
            f"GET /api/resource/{doctype} lieferte {liste.status_code}, erwartet 403"
        )
        detail = client.get(f"/api/resource/{doctype}/ein-beliebiger-name")
        assert detail.status_code == 403, (
            f"GET /api/resource/{doctype}/<name> lieferte {detail.status_code}, "
            "erwartet 403 (kein Mitglied-Durchreichen)"
        )

