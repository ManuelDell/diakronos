"""Eine Quelle der Wahrheit fuer Registrierungslinks (Befund 7, P0-4b).

Die Ableitung "Linktyp -> SPA-Seite" und "wie sieht die vollstaendige Adresse
aus" war an drei Stellen unabhaengig implementiert (create_link in
`api/registrierungslink_api.py`, `_normalisiere_link` in `api/admin_hub.py`,
`_link_seite`/`_link_anzeige` dort) und der Token-Erzeuger noch einmal. Jede
Aenderung musste an allen Stellen nachgezogen werden — der klassische Fall, in
dem eine Kopie irgendwann die falsche ist (UXD-R2/R3 sind genau so entstanden).

Hier steht die Ableitung EINMAL:

  * `neuer_token()` — der Zufallstoken eines neuen Links (`secrets.token_urlsafe`,
    10 Zeichen = ~80 Bit; unveraendert, damit bestehende Links gueltig bleiben).
  * `link_seite(typ)` — `gast` oder `registrierung`.
  * `link_anzeige(typ, slug)` — `/diakonos/<seite>?token=<slug>` (UXD-R3) oder
    `""` ohne Slug.
  * `normalisiere_link(link)` — setzt `link_anzeige` einer gelesenen Zeile auf
    die Standalone-Adresse; Altdaten trugen den relativen Frappe-Pfad.
  * `zustand(link, offene_anfragen=0)` — der Zustand einer Karte im
    Unterbereich „Links & QR-Codes“ (N3): aktiv / inaktiv / abgelaufen / voll,
    mit den Werten fuer den Platze-Balken und der Herkunft des Zustands.

Warum der Zustand hier steht: die Oberflaeche zeigt ihn an und der Server
entscheidet ihn — beide muessen dieselbe Regel benutzen. Vorher gab es die
Ableitung „was heisst abgelaufen/aktiv" NUR im oeffentlichen Pruefpfad
(`api/registrierung.py:_validate_token`); die Verwaltungsliste kannte sie nicht
und zeigte fuer abgelaufene Links einfach „aktiv“ (Konzept Abschnitt 5).
"""

from __future__ import annotations

import secrets
from datetime import date

__all__ = ["SEITE_GAST", "SEITE_REGISTRIERUNG", "TYPG_GAST", "neuer_token",
           "link_seite", "link_anzeige", "normalisiere_link", "zustand",
           "ZUSTAND_AKTIV", "ZUSTAND_INAKTIV", "ZUSTAND_ABGELAUFEN",
           "ZUSTAND_VOLL", "OFFENE_ANMELDESTATI"]

# SPA-Seiten der oeffentlichen Links.
SEITE_REGISTRIERUNG = "registrierung"
SEITE_GAST = "gast"

# Der Typ, der auf die Gast-Seite zeigt (Anzeige-Name aus der Frappe-Zeit).
TYPG_GAST = "Gast-Anmeldung"


def neuer_token() -> str:
    """Zufallstoken eines neuen Registrierungslink (~80 Bit).

    `validate_token` sucht `{"slug": token}` und jede neu angelegte Adresse
    braucht einen nicht erratbaren Wert; ohne Token war der Link nie nutzbar
    (UXD-R2).
    """
    return secrets.token_urlsafe(10)


def link_seite(typ) -> str:
    """SPA-Seite fuer einen Linktyp (`registrierung` oder `gast`)."""
    return SEITE_GAST if str(typ or "") == TYPG_GAST else SEITE_REGISTRIERUNG


def oeffentliche_basis() -> str:
    """Die gepflegte oeffentliche Adresse der Gemeinde (ohne Schluss-``/``).

    M-1: ``Einstellungen → Gemeinde → Öffentliche Adresse`` wird damit
    wirksam: geteilte Links zeigen auf genau diese Adresse. Ist die
    Einstellung leer, gibt die Funktion ``""`` zurueck und der Aufrufer
    faellt auf den relativen Pfad zurueck (die Oberflaeche ergaenzt dann
    ``window.location.origin``).

    Nie eine Exception: eine fehlende Einstellung darf die Linkanzeige nicht
    wegkaufen.
    """
    try:
        from diakronos_app.db import SessionLocal
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            return (zeile.oeffentliche_adresse or "").strip().rstrip("/") if zeile else ""
    except Exception:  # noqa: BLE001 — Einstellungen sind optional
        return ""


def link_anzeige(typ, slug) -> str:
    """Vollstaendige Adresse des Links fuer Anzeige/Kopieren (UXD-R3).

    Altdaten trugen hier einen relativen Pfad `/registrierung?token=…` aus der
    Frappe-Zeit; im Standalone gibt es die Seite nur unter `/diakonos/…`.
    Ohne Slug bleibt die Anzeige leer (kein toter Pfad).

    M-1: ist unter „Einstellungen → Gemeinde“ eine oeffentliche Adresse
    gepflegt, wird der Link ABSOLUT auf diese Adresse gebaut — so zeigt ein
    geteilter Link auf den Host, den die Gemeinde veroeffentlicht hat. Ohne
    gepflegte Adresse bleibt es der relative Pfad (die Oberflaeche ergaenzt
    den eigenen Ursprung).
    """
    wert = str(slug or "").strip()
    if not wert:
        return ""
    pfad = f"/diakonos/{link_seite(typ)}?token={wert}"
    basis = oeffentliche_basis()
    return f"{basis}{pfad}" if basis else pfad


def normalisiere_link(link: dict) -> dict:
    """`link_anzeige` einer gelesenen Zeile auf die Standalone-Adresse bringen.

    Nutzt dieselbe `link_anzeige` wie der Anlegepfad — deshalb koennen
    Altdaten, neu angelegte Links und die Kopier-Adresse nicht mehr
    auseinanderlaufen.
    """
    link["link_anzeige"] = link_anzeige(link.get("typ"), link.get("slug"))
    return link


# ── Zustand einer Linkkarte (N3) ───────────────────────────────────────────

# Die vier Zustaende, die die Verwaltung zeigt (Konzept Abschnitt 5).
ZUSTAND_AKTIV = "aktiv"
ZUSTAND_INAKTIV = "inaktiv"
ZUSTAND_ABGELAUFEN = "abgelaufen"
ZUSTAND_VOLL = "voll"

# Anmeldestati, die als „offene Anfrage“ gelten (wie `admin_hub` und N2).
OFFENE_ANMELDESTATI = ("Anmeldeanfrage", "Ausstehend")


def _als_datum(wert) -> date | None:
    """Datum/String -> `date`; unlesbare Werte ergeben `None`."""
    if not wert:
        return None
    if isinstance(wert, date):
        return wert
    try:
        return date.fromisoformat(str(wert)[:10])
    except ValueError:
        return None


def _ganzzahl(wert) -> int:
    """Zahl/String -> int; alles Unbrauchbare ergibt 0 (Altdaten sind schmutzig)."""
    try:
        return int(wert or 0)
    except (TypeError, ValueError):
        return 0


def zustand(link: dict, offene_anfragen: int = 0, heute: date | None = None) -> dict:
    """Zustand eines Registrierungslink fuer die Anzeige (N3, Konzept Abschnitt 5).

    Reihenfolge der Pruefung wie im oeffentlichen Pfad
    (`api/registrierung.py:_validate_token`), damit Anzeige und Wirkung nicht
    auseinanderlaufen: ausgeschaltet -> abgelaufen -> voll -> aktiv.

    Rueckgabe (alle Felder sind Anzeigewerte, keine Rechte):

        {
          "zustand": "aktiv" | "inaktiv" | "abgelaufen" | "voll",
          "abgelaufen": bool,           # auch bei inaktiv geprueft
          "voll": bool,                 # Kontingent aufgebraucht
          "plaetze_belegt": int,
          "plaetze_gesamt": int,        # 0 = unbegrenzt
          "anfragen_offen": int,
          # Nur wenn `aktiv` gesetzt ist, blendet ein Serverfilter auf
          # `aktiv = 1` diese Zeile aus — genau die Karten, die aus dem
          # eigenen Zustand ausgeblendet wuerden, muessen in einer
          # Zustandsliste erst recht sichtbar sein.
          "wuerde_ausgeblendet": bool,
        }
    """
    heute = heute or date.today()
    max_anmeldungen = _ganzzahl(link.get("max_anmeldungen"))
    belegt = _ganzzahl(link.get("anmeldungen_count"))
    aktiv = bool(_ganzzahl(link.get("aktiv")))
    bis = _als_datum(link.get("gueltig_bis"))

    abgelaufen = bool(bis and bis < heute)
    voll = bool(max_anmeldungen > 0 and belegt >= max_anmeldungen)

    if not aktiv:
        wert = ZUSTAND_INAKTIV
    elif abgelaufen:
        wert = ZUSTAND_ABGELAUFEN
    elif voll:
        wert = ZUSTAND_VOLL
    else:
        wert = ZUSTAND_AKTIV

    return {
        "zustand": wert,
        "abgelaufen": abgelaufen,
        "voll": voll,
        "plaetze_belegt": belegt,
        "plaetze_gesamt": max_anmeldungen,
        "anfragen_offen": _ganzzahl(offene_anfragen),
        "wuerde_ausgeblendet": not aktiv,
    }
