"""Zentrale Auslieferungsregel fuer Mitglied-Daten (B2).

Bewusste Datenschutz-Haertung gegenueber dem Frappe-Original:
api/mitglieder.py:190-234 liefert dort doc.as_dict() ohne Feldfilter;
get_adressbuch:579-593 erlaubt bei fehlenden Einstellungen Email/Telefon.
Hier gilt fail-closed: nur ein ausdrueckliches JSON-Boolean true gibt frei.
Admin-Rollen sehen alles (`permissions.is_admin`); Gruppenzugehoerigkeit und
Leitung erlauben keine Ausnahme. Eigene Daten bleiben vollstaendig.
Nullwerte erhalten die SPA-Struktur; Verwaltungsfelder werden weggelassen.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from .permissions import mitglied_permissions

SICHTBARKEIT_FELDER = ("email", "telefonnummer", "adresse", "geburtstag")
SICHTBARKEIT_DEFAULT = dict.fromkeys(SICHTBARKEIT_FELDER, False)
FELD_AN_SCHALTER = {
    "email": "email", "user": "email", "telefonnummer": "telefonnummer",
    "postleitzahl": "adresse", "wohnort": "adresse", "straße": "adresse",
    "nummer": "adresse", "geburtstag": "geburtstag",
}
VERWALTUNGSFELDER = (
    "notiz", "adressbuch_sichtbarkeit", "datenschutz_einwilligung",
    "datenschutz_datum", "foto_einwilligung", "foto_datum", "werbeeinwilligung",
    "werbung_datum", "widerrufen", "widerruf_datum", "widerruf_begruendung",
)


def sichtbarkeit_lesen(raw: Any) -> dict[str, bool]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = None
    if not isinstance(raw, Mapping):
        raw = {}
    return {feld: raw.get(feld) is True for feld in SICHTBARKEIT_FELDER}


def eigenes_mitglied_id() -> str | None:
    from .query import get_all, get_value
    from .session import session

    user = session.user
    if not user or user == "Guest":
        return None
    rows = get_all("Mitglied", filters={"user": user}, fields=["name"], limit_page_length=2)
    if rows:
        return str(rows[0]["name"]) if len(rows) == 1 else None
    email = get_value("User", user, "email") or user
    rows = get_all("Mitglied", filters={"email": email}, fields=["name", "user"],
                   limit_page_length=2)
    if len(rows) != 1 or rows[0].get("user"):
        return None
    return str(rows[0]["name"])


def ist_eigenes_mitglied(mitglied_id: Any) -> bool:
    return bool(mitglied_id) and str(mitglied_id) == eigenes_mitglied_id()


def darf_vertrauliches_sehen(mitglied_id: Any) -> bool:
    return ist_eigenes_mitglied(mitglied_id) or bool(
        mitglied_permissions(mitglied_id).get("can_view_sensitive")
    )


def maskiere_datensatz(
    datensatz: Mapping[str, Any] | None, *, mitglied_id: Any = None,
    vollstaendig: bool = False,
) -> dict[str, Any] | None:
    if datensatz is None:
        return None
    out = dict(datensatz)
    if vollstaendig:
        return out
    sicht = sichtbarkeit_lesen(out.get("adressbuch_sichtbarkeit"))
    if not sicht["email"]:
        # Account-/Metadaten duerfen die maskierte Email nicht duplizieren.
        for feld in ("owner", "modified_by"):
            if out.get(feld) and out[feld] in (out.get("email"), out.get("user")):
                out[feld] = None
    for feld, schalter in FELD_AN_SCHALTER.items():
        if feld in out and not sicht[schalter]:
            out[feld] = None
    for feld in VERWALTUNGSFELDER:
        out.pop(feld, None)
    return out


def maskiere_zeilen(
    zeilen: Iterable[Mapping[str, Any]], *, vollstaendig_ids: Iterable[Any] = (),
) -> list[dict[str, Any]]:
    erlaubt = {str(i) for i in vollstaendig_ids if i}
    return [maskiere_datensatz(z, vollstaendig=str(z.get("name")) in erlaubt) or {}
            for z in zeilen]
