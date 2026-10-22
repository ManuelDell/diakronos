"""Bericht fuer die KI — Markdown + JSON je Befund.

Der Bericht ist das Bindeglied zwischen dem Dev-Modus und einem Coding-Agenten:
er enthaelt je Befund den Text, die URL, den Element-Selektor samt
Komponentenkette, das Fehlerumfeld und die Bildpfade — so formuliert, dass eine
KI den Fehler ohne Rueckfrage findet.

Ablage: ``FILES_DIR/devmodus/<datum>/bericht.md`` (+ ``bericht.json``; Bilder
liegen bereits unter ``devmodus/<datum>/``).

Aufruf in der Oberflaeche (Admin-Download) und per CLI::

    python -m diakronos_app.devmodus.bericht [--offen] [--seit 2026-10-01] [--json]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app.settings import settings
from diakronos_app.devmodus import dienste
from diakronos_app.devmodus.einstellungen import FEHLER_ARTEN
from diakronos_app.devmodus.redaktion import redigiere


def _wurzel() -> Path:
    return Path(settings.files_dir).resolve() / "devmodus"


def erzeugen(sitzung: Session, *, seit: datetime | None = None,
             nur_offen: bool = False) -> dict[str, Any]:
    """Schreibt den Bericht und liefert Pfade + Kurzfassung zurueck."""
    daten = sammeln(sitzung, seit=seit, nur_offen=nur_offen)
    tag = datetime.now().strftime("%Y-%m-%d")
    ziel = _wurzel() / tag
    ziel.mkdir(parents=True, exist_ok=True)
    md_pfad = ziel / "bericht.md"
    json_pfad = ziel / "bericht.json"
    md_pfad.write_text(markdown(daten), encoding="utf-8")
    json_pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "bericht": str(md_pfad.relative_to(Path(settings.files_dir).resolve())),
        "json": str(json_pfad.relative_to(Path(settings.files_dir).resolve())),
        "pfad": str(md_pfad),
        "befunde": len(daten["befunde"]),
        "offen": len(daten["offene_befunde"]),
        "zeitpunkt": daten["zeitpunkt"],
    }


def sammeln(sitzung: Session, *, seit: datetime | None = None,
            nur_offen: bool = False) -> dict[str, Any]:
    """Rohdaten des Berichts (redigiert)."""
    from diakronos_app.models.devmodus import DevBefund

    frage = select(DevBefund)
    if seit is not None:
        frage = frage.where(DevBefund.zeitpunkt >= seit)
    if nur_offen:
        frage = frage.where(DevBefund.status.in_(["offen", "an_claude"]))
    befunde = list(sitzung.scalars(frage.order_by(DevBefund.zeitpunkt)).all())

    zeilen = [_befund_zeile(b) for b in befunde]
    return {
        "zeitpunkt": datetime.now().isoformat(timespec="seconds"),
        "filter": {"seit": seit.isoformat() if seit else None, "offen": nur_offen},
        "kennzahlen": dienste.zaehle(sitzung),
        "befunde": zeilen,
        "offene_befunde": [z for z in zeilen if z["status"] in ("offen", "an_claude")],
    }


def _befund_zeile(b) -> dict[str, Any]:
    element = b.element or {}
    return {
        "name": b.name, "titel": redigiere(b.titel), "text": redigiere(b.text),
        "art": b.art, "wichtigkeit": b.wichtigkeit, "status": b.status,
        "benutzer": b.benutzer, "zeitpunkt": b.zeitpunkt.isoformat() if b.zeitpunkt else None,
        "url": redigiere(b.url), "route": b.route, "seite": b.seite,
        "seitentitel": redigiere(b.seitentitel),
        "umgebung": {
            "viewport": b.viewport, "bildschirm": b.bildschirm,
            "geraet": b.geraet, "browser": b.browser, "theme": b.theme,
            "sprache": b.sprache,
        },
        "element": {
            "selektor": element.get("selektor"),
            "tag": element.get("tag"),
            "id": element.get("id"),
            "klassen": element.get("klassen"),
            "komponenten": element.get("komponenten"),
            "text": element.get("text"),
            "aria_label": element.get("aria_label"),
            "role": element.get("role"),
            "position": element.get("position"),
            "stile": element.get("stile"),
            "outer_html": element.get("outer_html"),
            "datenattribute": element.get("datenattribute"),
        } if element else None,
        "bilder": b.bilder or [],
        "audio": b.audio,
        "fehlerumfeld": [
            {"art": e.get("art"), "methode": e.get("methode"), "pfad": e.get("pfad"),
             "status": e.get("status"), "meldung": e.get("meldung"),
             "request_id": e.get("request_id"), "traceback": e.get("traceback")}
            for e in (b.fehlerumfeld or [])
        ],
        "fehler": len([e for e in (b.fehlerumfeld or []) if e.get("art") in FEHLER_ARTEN]),
    }


def markdown(daten: dict[str, Any]) -> str:
    k = daten["kennzahlen"]
    zeilen = [
        "# Diakronos — Dev-Befunde",
        "",
        f"Erstellt: {daten['zeitpunkt']}",
        f"Befunde: {len(daten['befunde'])}  ·  Offen: {len(daten['offene_befunde'])}",
        f"Gesamt: {k['gesamt']}  ·  an Claude: {k['an_claude']}"
        f"  ·  behoben: {k['behoben']}  ·  verworfen: {k['verworfen']}",
        "",
    ]
    if daten["filter"].get("seit"):
        zeilen += [f"Nur Befunde seit: {daten['filter']['seit']}", ""]
    if not daten["befunde"]:
        zeilen += ["Keine Befunde im Filter.", ""]
    for b in daten["befunde"]:
        zeilen += _befund_markdown(b)
    return "\n".join(zeilen) + "\n"


def _befund_markdown(b: dict[str, Any]) -> list[str]:
    el = b.get("element") or {}
    z = [
        f"## {b['titel'] or b['name']}  ({b['art']}, {b['wichtigkeit']}, {b['status']})",
        "",
        f"**Was:** {b['text'] or '—'}",
        "",
        f"- Befund: `{b['name']}`  ·  von: {b['benutzer']}  ·  Zeit: {b['zeitpunkt']}",
        f"- URL: {b['url'] or '—'}",
        f"- Route: {b['route'] or '—'}  ·  Seite: {b['seite'] or '—'}"
        f"  ·  Titel: {b['seitentitel'] or '—'}",
        f"- Fenster: {b['umgebung']['viewport'] or '—'}"
        f"  ·  Bildschirm: {b['umgebung']['bildschirm'] or '—'}"
        f"  ·  Gerät: {b['umgebung']['geraet'] or '—'}",
        f"- Browser: {b['umgebung']['browser'] or '—'}"
        f"  ·  Theme: {b['umgebung']['theme'] or '—'}"
        f"  ·  Sprache: {b['umgebung']['sprache'] or '—'}",
        "",
    ]
    if el:
        z += [
            "### Element",
            "",
            f"- Selektor: `{el.get('selektor') or '—'}`",
            f"- Tag: `{el.get('tag') or '—'}`  ·  id: `{el.get('id') or '—'}`",
            f"- Klassen: {el.get('klassen') or '—'}",
            f"- Komponentenkette: {' > '.join(el.get('komponenten') or []) or '—'}",
            f"- Text: {el.get('text') or '—'}",
            f"- aria-label: {el.get('aria_label') or '—'}  ·  role: {el.get('role') or '—'}",
            f"- Position: {el.get('position') or '—'}",
            f"- Stile: {el.get('stile') or '—'}",
        ]
        if el.get("datenattribute"):
            z.append(f"- data-*: {el['datenattribute']}")
        if el.get("outer_html"):
            z += ["", "```html", str(el["outer_html"])[:2000], "```"]
        z.append("")
    if b.get("bilder"):
        z += ["### Bilder", ""]
        z += [f"- `{p}`" for p in b["bilder"]]
        z.append("")
    if b.get("audio"):
        z += [f"### Audio", "", f"- `{b['audio'].get('pfad')}` ({b['audio'].get('typ')})", ""]
    if b.get("fehlerumfeld"):
        z += [f"### Fehlerumfeld ({b['fehler']} Fehler, letzte 60 s)", ""]
        for e in b["fehlerumfeld"]:
            z.append(f"- {e['art']}: {e['methode'] or ''} {e['pfad'] or ''} "
                     f"→ {e['status'] if e['status'] is not None else ''} "
                     f"· Request-ID {e['request_id'] or '—'}")
            if e.get("meldung"):
                z.append(f"  - {e['meldung']}")
            if e.get("traceback"):
                z += ["", "```", str(e["traceback"])[:2000], "```"]
        z.append("")
    z.append("---")
    z.append("")
    return z


def _cli() -> int:
    """``python -m diakronos_app.devmodus.bericht [--offen] [--seit DATUM] [--json]``."""
    parser = argparse.ArgumentParser(description="Diakronos Dev-Befundbericht erzeugen")
    parser.add_argument("--offen", action="store_true",
                        help="Nur offene Befunde ausgeben (kein Schreiben).")
    parser.add_argument("--seit", default=None, help="Nur Befunde ab ISO-Datum.")
    parser.add_argument("--json", action="store_true", help="JSON statt Markdown ausgeben.")
    parser.add_argument("--schreiben", action="store_true",
                        help="Bericht zusaetzlich in FILES_DIR ablegen.")
    args = parser.parse_args()

    seit = None
    if args.seit:
        try:
            seit = datetime.fromisoformat(args.seit)
        except ValueError:
            print(f"Ungueltiges Datum: {args.seit!r} (ISO erwartet, z. B. 2026-10-01)")
            return 2

    from diakronos_app import db

    with db.SessionLocal() as sitzung:
        if args.schreiben:
            ergebnis = erzeugen(sitzung, seit=seit, nur_offen=args.offen)
            print(f"Bericht: {ergebnis['pfad']}")
            return 0
        daten = sammeln(sitzung, seit=seit, nur_offen=args.offen)
        if args.json:
            print(json.dumps(daten, ensure_ascii=False, indent=2))
        elif args.offen:
            for b in daten["offene_befunde"]:
                print(f"[{b['status']}] {b['seite'] or b['url'] or '—'}: {b['titel']}\n"
                      f"    {(b['text'] or '').strip()[:400]}")
            print(f"\n{len(daten['offene_befunde'])} offene Befunde.")
        else:
            print(markdown(daten))
    return 0


def main() -> int:
    return _cli()


if __name__ == "__main__":  # pragma: no cover - CLI-Einstieg
    raise SystemExit(main())
