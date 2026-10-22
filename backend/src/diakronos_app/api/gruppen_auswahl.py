"""B-1/B-2/J: Waehlbare Mitglieder fuer die Gruppen-Auswahl.

Diese Funktion ist die EINE Stelle, an der die Auswahlliste "Mitglied
hinzufuegen" ihren Personenbestand liest. Sie liefert bewusst NUR `mitglied`
und `name` — die E-Mail ist ein Adressbuch-Feld (Regel B2,
`frappe_compat/mitglied_sichtbarkeit.py`) und gehoert nicht in eine Liste,
die ein Gruppenverantwortlicher sehen darf. Weil die E-Mail hier fehlt, ist
sie auch kein Suchfeld: sonst waere die Suche ein Seitenkanal genau auf das
Feld, das `get_mitglieder_liste` fuer Nicht-Admins abschneidet.

Gesucht wird in Vor- und Nachname, umlaut- und gross-klein-unabhaengig —
mit derselben Faltung, die `api/mitglieder.py` (`_suche_normalisieren`,
`_suche_ausdruck`) fuer die Mitgliedersuche benutzt, damit es nicht zwei
Regeln fuer dieselbe Frage gibt. Statt eines zweiten `LIKE`-Ausdrucks im
Query-Layer geht der Weg bewusst ueber `db.sql` (gebundene Parameter), genau
wie die (getestete) Mitgliedersuche.

Ausgetretene und verstorbene Personen werden NICHT angeboten: die Liste
dient dem Aufnehmen in eine Gruppe, dafuer ist ein ausgeschiedener Mensch
keine sinnvolle Auswahl.
"""
from __future__ import annotations

import unicodedata
from typing import Any

from diakronos_app.frappe_compat import db

# Dieselbe Faltung wie `api/mitglieder.py` (BF1-J). Reihenfolge ist wichtig:
# zuerst BEIDE Schreibweisen der Umlaute/ß ersetzen, erst danach LOWER.
_FALTUNG = (("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"),
            ("ä", "ae"), ("ö", "oe"), ("ü", "ue"))

# Status, die nicht mehr waehlbar sind (kleingeschrieben verglichen).
# „ausgetreten“ kommt mit der Karte AUSTRITT dazu (`api/austritt.py` setzt ihn;
# ohne diesen Eintrag bliebe eine ausgetretene Person in jeder Auswahlliste).
AUSGESCHIEDEN = {"ausgetreten", "verstorben", "verstorben/ausgetreten", "geloescht"}


def _sql_ausdruck(spalte: str) -> str:
    """SQL-Ausdruck, der eine Spalte klein- UND umlautgefaltet liefert.

    Kein Nutzereingabe-Anteil — `spalte` ist ein fester Bezeichner dieser
    Datei (kein Injection-Pfad). Gleichwertig zu
    `api/mitglieder._suche_ausdruck`.
    """
    ausdruck = spalte
    for von, nach in _FALTUNG:
        ausdruck = f"REPLACE({ausdruck}, '{von}', '{nach}')"
    return f"LOWER({ausdruck})"


def _normalisieren(text: Any) -> str:
    """Python-Gegenstueck zur SQL-Faltung (gleiches Ergebnis).

    K8: wie `api/mitglieder._suche_normalisieren` — erst NFC + Trim, dann
    falten; sonst laufen serverseitige Suche und SPA-Feinfilter auseinander.
    """
    wert = unicodedata.normalize("NFC", str(text or "")).strip()
    for von, nach in _FALTUNG:
        wert = wert.replace(von, nach)
    return wert.lower()


def waehlbare_mitglieder(suche: str = "", limit: int = 0) -> list[dict[str, str]]:
    """Waehlbare Mitglieder als `[{"mitglied", "name"}]`, optional gefiltert.

    `limit=0` bedeutet: keine Abschneidung. Die Filterung laeuft serverseitig
    (SQL, umlautgefaltet); das ist die Voraussetzung dafuer, dass eine Gemeinde
    mit mehr als 50 Mitgliedern jede Person auswaehlen kann (B-2).
    """
    treffer = _normalisieren(suche)
    grenze = max(int(limit or 0), 0)

    params: dict[str, Any] = {}
    suche_glied = "1=1"
    woerter = treffer.split()
    if woerter:
        glieder = []
        for i, wort in enumerate(woerter):
            key = f"suche_{i}"
            params[key] = f"%{wort}%"
            glieder.append(
                f"({_sql_ausdruck('m.vorname')} LIKE %({key})s "
                f"OR {_sql_ausdruck('m.nachname')} LIKE %({key})s)"
            )
        suche_glied = " AND ".join(glieder)

    # Ausgeschiedene herausfiltern: der Status ist Stammdatenfeld, keine
    # Sichtbarkeitsfrage. `status` darf NULL sein (noch nie gepflegt) — solche
    # Zeilen bleiben waehlbar (COALESCE auf '').
    status_glied = " AND COALESCE(LOWER(TRIM(m.status)), '') NOT IN ({})".format(
        ", ".join(f"'{s}'" for s in sorted(AUSGESCHIEDEN))
    )

    query = f"""
        SELECT
            m.name,
            m.vorname,
            m.nachname,
            CONCAT_WS(' ', NULLIF(m.vorname, ''), NULLIF(m.nachname, '')) AS anzeigename
        FROM mitglied m
        WHERE 1=1
          AND {suche_glied}
          {status_glied}
        ORDER BY m.nachname ASC, m.vorname ASC, m.name ASC
    """
    rows = db.sql(query, params, as_dict=True) or []

    ergebnis: list[dict[str, str]] = []
    for m in rows:
        mid = str(m.get("name") or "")
        if not mid:
            continue
        name = str(m.get("anzeigename") or "").strip() or mid
        # Feinfilter in Python: `LIKE` ist je nach Datenbank unterschiedlich
        # genau; hier entscheidet die gefaltete Form, damit das Ergebnis
        # zwischen Postgres und SQLite gleich ist.
        if any(wort not in _normalisieren(name) for wort in woerter):
            continue
        ergebnis.append({"mitglied": mid, "name": name})
        if grenze and len(ergebnis) >= grenze:
            break

    return ergebnis
