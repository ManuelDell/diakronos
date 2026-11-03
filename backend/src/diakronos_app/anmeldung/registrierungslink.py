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
from datetime import date, datetime

__all__ = ["SEITE_GAST", "SEITE_REGISTRIERUNG", "TYPG_GAST", "neuer_token",
           "TOKEN_LAENGE", "TOKEN_MINDESTLAENGE",
           "link_seite", "link_anzeige", "normalisiere_link", "zustand",
           "jetzt_gemeinde", "heute_gemeinde",
           "ZUSTAND_AKTIV", "ZUSTAND_INAKTIV", "ZUSTAND_ABGELAUFEN",
           "ZUSTAND_VOLL", "ZUSTAND_BEVORSTEHEND", "OFFENE_ANMELDESTATI"]

# SPA-Seiten der oeffentlichen Links.
SEITE_REGISTRIERUNG = "registrierung"
SEITE_GAST = "gast"

# Der Typ, der auf die Gast-Seite zeigt (Anzeige-Name aus der Frappe-Zeit).
TYPG_GAST = "Gast-Anmeldung"


def neuer_token() -> str:
    """Zufallstoken eines neuen Registrierungslink (256 Bit, SEC-3).

    `validate_token` sucht `{"slug": token}` und jede neu angelegte Adresse
    braucht einen nicht erratbaren Wert; ohne Token war der Link nie nutzbar
    (UXD-R2).

    SEC-3 (Pentest dev.ecg-hn.de, MITTEL): hier stand `token_urlsafe(10)` —
    rund 60 Bit, und der Slug liess sich beim Anlegen ausserdem frei
    vorgeben („pt-mitglied“). Beides zusammen machte Registrierungslinks
    erratbar. Jetzt 32 Zufallsbytes = 43 Zeichen base64url (~256 Bit); der
    Wert ist fuer Menschen nicht mehr tippbar und wird nur noch kopiert.

    BESTEHENDE Links bleiben gueltig: gelesen wird `slug` unveraendert, die
    Laenge wird nirgends geprueft. Betroffen ist ausschliesslich die
    NEUANLAGE.
    """
    return secrets.token_urlsafe(32)


#: Laenge eines Tokens aus `neuer_token()` (`run(secrets.token_urlsafe(32))`).
TOKEN_LAENGE = 43
#: Kleinste akzeptable Laenge fuer einen VOM SERVER erzeugten Token. Die
#: Grenze steht hier, damit „stark“ eine pruefbare Zahl hat und nicht nur
#: eine Absicht ist (`len(neuer_token()) >= TOKEN_MINDESTLAENGE`).
TOKEN_MINDESTLAENGE = 32


def link_seite(typ) -> str:
    """SPA-Seite fuer einen Linktyp (`registrierung` oder `gast`)."""
    return SEITE_GAST if str(typ or "") == TYPG_GAST else SEITE_REGISTRIERUNG


def oeffentliche_basis(session=None) -> str:
    """Die gepflegte oeffentliche Adresse der Gemeinde (ohne Schluss-``/``).

    M-1: ``Einstellungen → Gemeinde → Öffentliche Adresse`` wird damit
    wirksam: geteilte Links zeigen auf genau diese Adresse. Ist die
    Einstellung leer, gibt die Funktion ``""`` zurueck und der Aufrufer
    faellt auf den relativen Pfad zurueck (die Oberflaeche ergaenzt dann
    ``window.location.origin``).

    Nie eine Exception: eine fehlende Einstellung darf die Linkanzeige nicht
    wegkaufen.

    ``session`` (BS-1b2/F2): eine bereits offene Sitzung. Ohne sie oeffnet die
    Funktion eine EIGENE — richtig fuer einen einzelnen Aufruf, falsch in
    einer Schleife ueber viele Zeilen (je Aufruf eine Abfrage). Die
    oeffentliche Lese-API reicht deshalb ihre Lesesitzung herein.
    """
    try:
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        if session is not None:
            zeile = session.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            return (zeile.oeffentliche_adresse or "").strip().rstrip("/") if zeile else ""

        from diakronos_app.db import SessionLocal

        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            return (zeile.oeffentliche_adresse or "").strip().rstrip("/") if zeile else ""
    except Exception:  # noqa: BLE001 — Einstellungen sind optional
        return ""


def link_anzeige(typ, slug, session=None, basis: str | None = None) -> str:
    """Vollstaendige Adresse des Links fuer Anzeige/Kopieren (UXD-R3).

    Altdaten trugen hier einen relativen Pfad `/registrierung?token=…` aus der
    Frappe-Zeit; im Standalone gibt es die Seite nur unter `/diakonos/…`.
    Ohne Slug bleibt die Anzeige leer (kein toter Pfad).

    M-1: ist unter „Einstellungen → Gemeinde“ eine oeffentliche Adresse
    gepflegt, wird der Link ABSOLUT auf diese Adresse gebaut — so zeigt ein
    geteilter Link auf den Host, den die Gemeinde veroeffentlicht hat. Ohne
    gepflegte Adresse bleibt es der relative Pfad (die Oberflaeche ergaenzt
    den eigenen Ursprung).

    ``session``/``basis`` (BS-1b2/F2): offene Sitzung des Aufrufers bzw. die
    bereits gelesene oeffentliche Adresse. Ohne beides wird beides neu
    gelesen — richtig fuer einen einzelnen Aufruf, falsch in einer Schleife
    ueber viele Zeilen (dann je Zeile eine Abfrage).
    """
    wert = str(slug or "").strip()
    if not wert:
        return ""
    # WEB-5a: unter dem Betriebs-Praefix liegt die Seite unter
    # `/diakonos/diakonos/…` — der Link muss genau dorthin zeigen.
    from diakronos_app import base_path

    pfad = base_path.pfad(f"/diakonos/{link_seite(typ)}?token={wert}")
    if basis is None:
        try:
            basis = oeffentliche_basis(session)
        except TypeError:
            # Ein Ersatz ohne Parameter (Tests/aeltere Aufrufer) bleibt
            # gueltig — der Vertrag war vor BS-1b2 `oeffentliche_basis()`.
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
# REG-1a: „gueltig ab“ liegt in der Zukunft — fuer Besucher noch nicht nutzbar.
ZUSTAND_BEVORSTEHEND = "bevorstehend"

# Anmeldestati, die als „offene Anfrage“ gelten (wie `admin_hub` und N2).
OFFENE_ANMELDESTATI = ("Anmeldeanfrage", "Ausstehend")


# ── Zeit der Gemeinde: EINE Quelle fuer Anzeige und Wirkung (REG-1c) ───────
#
# Bis REG-1b rechneten zwei Stellen die Zeitzone selbst aus: `heute_gemeinde`
# hier (Anzeige-Zustand) und `heute_ortszeit`/`_heute_gemeinde` in
# `api.registrierung` (Wirkung von „gueltig ab/bis“). Beide Kopien waren
# gleich — aber eine Aenderung an einer Stelle haette Anzeige und Wirkung
# auseinanderlaufen lassen (genau der Fehler, den dieses Modul sonst
# vermeidet). Die Rechnung steht deshalb NUR noch hier; `api.registrierung`
# reicht sie unter den gewohnten Namen weiter (Tests und Aufrufer bleiben).


def jetzt_gemeinde() -> datetime:
    """Jetzt in der Zeitzone der Gemeinde (``settings.calendar_timezone``).

    Der Container laeuft in UTC; eine Gemeinde in Europe/Berlin liegt damit um
    Mitternacht zwei Stunden zurueck. Ist die Einstellung unbrauchbar, gilt
    UTC (nie eine Exception: eine kaputte Zeitzone darf keinen Link toeten).
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from diakronos_app.settings import settings

    try:
        zone = ZoneInfo(str(getattr(settings, "calendar_timezone", "") or "UTC"))
    except (ValueError, ZoneInfoNotFoundError):
        zone = ZoneInfo("UTC")
    return datetime.now(zone)


def heute_gemeinde(jetzt: datetime | None = None) -> date:
    """HEUTE in der Zeitzone der Gemeinde — nie ``date.today()`` des Containers.

    Der Container laeuft in UTC; eine Gemeinde in Europe/Berlin liegt damit um
    Mitternacht zwei Stunden „hinterher“. Mit ``date.today()`` begann ein Link
    „gueltig ab 26.10.“ erst um 02:00 Ortszeit und lief entsprechend zu lang
    (Operator-Review REG-1a, Punkt 5). EINE Quelle fuer Anzeige (``zustand``)
    und Wirkung (``api.registrierung._validate_token``).

    ``jetzt`` dient Tests, die den Mitternachtsfall festnageln muessen.
    """
    return (jetzt or jetzt_gemeinde()).date()


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
    auseinanderlaufen: ausgeschaltet -> abgelaufen -> bevorstehend -> voll -> aktiv.

    Rueckgabe (alle Felder sind Anzeigewerte, keine Rechte):

        {
          "zustand": "aktiv" | "inaktiv" | "abgelaufen" | "bevorstehend" | "voll",
          "abgelaufen": bool,           # auch bei inaktiv geprueft
          "bevorstehend": bool,         # REG-1a: `gueltig_ab` liegt in der Zukunft
          "gueltig_ab": str | None,     # ISO-Datum oder None (sofort)
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
    heute = heute or heute_gemeinde()
    max_anmeldungen = _ganzzahl(link.get("max_anmeldungen"))
    belegt = _ganzzahl(link.get("anmeldungen_count"))
    aktiv = bool(_ganzzahl(link.get("aktiv")))
    bis = _als_datum(link.get("gueltig_bis"))
    ab = _als_datum(link.get("gueltig_ab"))

    abgelaufen = bool(bis and bis < heute)
    # REG-1a: der Link ist erst AB diesem Tag nutzbar; am Tag selbst schon.
    bevorstehend = bool(ab and ab > heute)
    voll = bool(max_anmeldungen > 0 and belegt >= max_anmeldungen)

    if not aktiv:
        wert = ZUSTAND_INAKTIV
    elif abgelaufen:
        wert = ZUSTAND_ABGELAUFEN
    elif bevorstehend:
        wert = ZUSTAND_BEVORSTEHEND
    elif voll:
        wert = ZUSTAND_VOLL
    else:
        wert = ZUSTAND_AKTIV

    return {
        "zustand": wert,
        "abgelaufen": abgelaufen,
        "bevorstehend": bevorstehend,
        "gueltig_ab": ab.isoformat() if ab else None,
        "voll": voll,
        "plaetze_belegt": belegt,
        "plaetze_gesamt": max_anmeldungen,
        "anfragen_offen": _ganzzahl(offene_anfragen),
        "wuerde_ausgeblendet": not aktiv,
    }
