"""PERF-K2 — Vorabladen fuer Rechte-Fragen, die von LISTEN abhaengen.

BEFUND (Karte PERF-K2, gemessen im Vorbau-Image mit dem PERF-K1-Aufbau:
10 Kalender / 50 Nutzer / 312 Termine):

  * `get_calendar_events` fragte den Rechte-Kern 120x je Monatsansicht
    (`darf` 40, `pruefstufen` 50, `moderationsstufen` 40 — je Kalender 4x
    `darf` + 5x Stufen). Rechte-Regeln sind das NICHT: es war die Zahl der
    Aufrufe. PERF-K1 hat die Fragen JE TERMIN beseitigt; was blieb, ist EINE
    Frage JE KALENDER, und die ist selbst schon teuer (je Frage: ganz
    `Mitglied` + ganz `User`, weil `benutzer_status._kontozustand` bei
    ungeflushten Aenderungen NICHT merkt).
  * Dazu kam ein Wiederholer IM Terminweg: der Anzeigename des Kalenders
    wurde je Termin erneut per `get_value("Kalender", ...)` gelesen
    (276 Abfragen fuer EINE Monatsansicht).

Dieses Modul aendert KEINE Rechte-Entscheidung. Es stellt nur die Antworten
vorab bereit, die der Rechte-Kern ohnehin gleich geben wird — unter
DENSELBEN Merker-Schluesseln, die `rechte.kern` benutzt
(`_MERKER`/`_gemerkt` aus PERF-K1). Entschieden wird danach unveraendert von
`rechte.darf`, `pruefstufen` und `moderationsstufen`; ohne Merkungsrahmen tut
die Funktion nichts, und wo die Einzelfrage nicht eindeutig nachgebildet
werden kann, wird NICHTS gemerkt (dann laeuft die Einzelfrage wie bisher).

Gleichheit ist die Pflicht: `tests/test_perf_k2_kalender_gleichheit.py`
vergleicht die Antwort jedes Kalenders mit und ohne Vorabladen.

PERF-K2b (Review R2, MUSS 1): Es gibt hier KEINE Ablage „aus der Liste“ mehr.
Ein Vorrat aus den FERTIGEN Eintraegen von `get_accessible_calendars` waere
eine ZWEITE RECHTEREGEL: die Liste rechnet `write = pruefstufen or
darf(SCHREIBEN) or darf(VORSCHLAGEN)` — wer das als `darf(SCHREIBEN)`
zuruecklegt, macht aus „ich moderiere“ ein „ich darf schreiben“ (der
Kurzschluss im `or` hat `darf(SCHREIBEN)` nie gefragt). Genau so vergiftete
der Nachtrag aus R1 den Merker (Kalenderadministrator auf oeffentlichem
Kalender, Mitglied mit Einzelfreigabe „moderieren“). Hier stehen deshalb nur
noch Antworten des Kerns (`_darf_roh`, `_pruefstufen_roh`,
`_moderationsstufen_roh`) und belegte Tatsachen (Existenz).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

__all__ = [
    "kalender_existiert",
    "kalender_existenz_merken",
    "kalender_rechte_vorladen",
]

EXISTENZ_SCHLUESSEL = ("kalender_existiert",)


def kalender_existiert(name: Any) -> bool:
    """Gibt es diesen Kalender? (Merker-Schluessel `kalender_existiert`.)

    Alte Regel: `permissions.hat_leserecht`/`moderation.*` lasen die Liste
    `get_accessible_calendars`, die nur EXISTIERENDE Kalender enthaelt. Eine
    Einzelfrage an `rechte.darf` allein wuerde das verlieren — `_darf_roh`
    antwortet dem Admin JA, BEVOR es das Objekt prueft. Diese Frage ist
    deshalb ueberall Vorbedingung (wie `hat_leserecht_fuer`).

    Gemerkt wird die Antwort je Aufruf und Name; sie haengt nur am Bestand,
    nicht am Benutzer. Ohne Merkungsrahmen wird wie zuvor jedes Mal gelesen.
    """
    from diakronos_app.rechte import kern

    schluessel = (*EXISTENZ_SCHLUESSEL, str(name or ""))

    def _lesen() -> bool:
        from diakronos_app.frappe_compat.api_helpers import get_value

        return bool(get_value("Kalender", str(name), "name"))

    return bool(kern._gemerkt(schluessel, _lesen))


def kalender_existenz_merken(namen: Iterable[Any]) -> None:
    """Existenz fuer VIELE Kalender in EINER Abfrage merken (statt je Name).

    Nur wer alle Kalender-Zeilen ohnehin gelesen hat (`get_accessible_calendars`),
    darf das aufrufen: `namen` muessen die GESAMTE Kalenderliste sein, sonst
    bekaeme ein vorhandener, aber hier fehlender Kalender faelschlich "nein".
    """
    from diakronos_app.rechte import kern

    merker = kern._MERKER.get()
    if merker is None:
        return
    for name in namen:
        merker.setdefault((*EXISTENZ_SCHLUESSEL, str(name or "")), True)


def _existenz_abfragen(namen: list[str]) -> None:
    """Existenz fuer `namen` in EINER Sammelabfrage merken (nicht je Name)."""
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.rechte import kern

    merker = kern._MERKER.get()
    if merker is None or not namen:
        return
    offen = [n for n in namen if (*EXISTENZ_SCHLUESSEL, n) not in merker]
    if not offen:
        return
    with lesesitzung() as sess:
        vorhanden = {str(n) for n in sess.execute(
            select(Kalender.name).where(Kalender.name.in_(offen))).scalars()}
    for name in offen:
        merker[(*EXISTENZ_SCHLUESSEL, name)] = name in vorhanden


def kalender_rechte_vorladen(benutzer: str | None, kalender: Iterable[Any]) -> None:
    """Antworten des Rechte-Kerns fuer VIELE Kalender in wenigen Abfragen merken.

    `kalender` sind Namen oder Kalender-Zeilen (`dict`/Objekt mit `name`); was
    nicht lesbar ist, wird uebersprungen. Gemerkt werden — je Kalender und
    Aufrufer, unter den Schluesseln von `rechte.kern._gemerkt`:

      * `modul_aktiv`                (je Gruppe/Modul, nur wo ein Objekt existiert)
      * `objekt_kontext`             (Objekt-Zeile + Stufen-Kontext)
      * `darf` fuer lesen/schreiben/vorschlagen/moderieren/verwalten
      * `pruefstufen`, `moderationsstufen`

    Die Rechnung selbst ist die des Kerns: `_darf_roh`,
    `_pruefstufen_roh`, `_moderationsstufen_roh` — hier steht KEINE zweite
    Rechteregel, nur ein Vorrat. Vorhandene Merker-Eintraege werden nie
    ueberschrieben; das Vorabladen greift also nie in eine frueher gegebene
    Antwort ein.
    """
    from diakronos_app.rechte import kern

    merker = kern._MERKER.get()
    if merker is None or not benutzer or benutzer == kern.GAST:
        return
    # Ein Login ohne Konto/Mitglied ist niemand: dort wird NICHTS vorab
    # beantwortet. Die Einzelfrage entscheidet so wie bisher (fail closed) —
    # dieser Kurzweg haelt nur den Volllauf `benutzer_status` aus dem Vorrat.
    if not kern._ist_angemeldetes_mitglied(benutzer):
        return

    typ = "kalender"
    modul = kern.TYP_MODUL.get(typ)
    namen = sorted({
        str(k if isinstance(k, str) else getattr(k, "name", k) or "")
        for k in kalender
    } - {""})
    if not namen:
        return

    # Existenz: fuer JEDEN Namen in EINER Sammelabfrage merken — die
    # Einzelfragen (`hat_leserecht`, `ist_moderator`) pruefen sie als
    # Vorbedingung und sollen dafuer nicht je Name nachfragen. Kalender mit
    # Rechte-Objekt bekommen sie unten ohnehin.
    _existenz_abfragen(namen)

    class _Zeile:
        """Attribut-Zugriff auf eine Zeilenkopie (wie das ORM-Objekt)."""

        __slots__ = ("_d",)

        def __init__(self, d: dict[str, Any]) -> None:
            self._d = d

        def __getattr__(self, name: str) -> Any:
            try:
                return self._d[name]
            except KeyError as exc:  # wie beim ORM: kein Attribut = Fehler
                raise AttributeError(name) from exc

    # ── Objekt-Zeilen: EIN Zugriff auf die Tabelle ──
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.models.rechte import RechteFreigabe, RechteObjekt

    with lesesitzung() as sess:
        # Nur ZEILENKOPIEN: die Sitzung wird geschlossen, die Einzelfrage
        # liefert dagegen gebundene Objekte. Beides ist fuer den Kern gleich
        # (`_objekt`/`_freigaben_roh` lesen nur Attribute), die Kopie haelt
        # aber keine Sitzung offen und ueberlebt auch ein `expire` nach Commit.
        objekte = {
            str(o.objekt): dict(
                typ=o.typ, objekt=o.objekt, gruppe=o.gruppe,
                untergruppe=o.untergruppe,
                standard_gruppe_lesen=o.standard_gruppe_lesen,
                gemeinde_status=o.gemeinde_status, gruppe_status=o.gruppe_status,
                eltern_typ=o.eltern_typ, eltern_objekt=o.eltern_objekt,
            )
            for o in sess.execute(
                select(RechteObjekt).where(
                    RechteObjekt.typ == typ, RechteObjekt.objekt.in_(namen))
            ).scalars()
        }

        # PERF-K4a: Freigabe-Zeilen ALLER Kalender in EINER Abfrage. **Nur
        # ergaenzt, wenn der Merker sie noch nicht hat** — ein vorhandener
        # Eintrag wird nie ueberschrieben (dieselbe Zusage wie oben fuer
        # `objekt_kontext`). `_freigaben_roh` und
        # `_leitung_mit_gruppenfreigabe` lesen daraus dieselben Felder, die sie
        # bisher vom ORM-Objekt lasen; abgeleitet wird NICHTS (kein
        # `darf`-Ergebnis aus der Freigabe).
        offen = [n for n in namen if ("freigabe_zeilen", typ, n) not in merker]
        if offen:
            vorhandene = {}
            for fg in sess.execute(
                select(RechteFreigabe).where(
                    RechteFreigabe.typ == typ, RechteFreigabe.objekt.in_(offen))
            ).scalars():
                vorhandene.setdefault(str(fg.objekt), []).append(dict(
                    benutzer=fg.benutzer, gruppe=fg.gruppe,
                    lesen=fg.lesen, schreiben=fg.schreiben,
                    moderieren=fg.moderieren,
                ))
            for name in offen:
                merker[("freigabe_zeilen", typ, name)] = [
                    _Zeile(z) for z in vorhandene.get(name, [])
                ]

    # ── Gruppen/Module der Objekte vorab (2 Abfragen) ──
    gruppen = sorted({str(o["gruppe"]) for o in objekte.values() if o["gruppe"]})
    vorladen = getattr(kern, "rollen_vorladen", None)
    if gruppen and modul and vorladen is not None:
        vorladen(benutzer, gruppen=gruppen, module=[modul])

    for name in namen:
        if name not in objekte:
            # Kein Rechte-Objekt: die Sammelabfrage oben belegt das bereits —
            # `_objekt` soll dafuer nicht je Name nachfragen. `_darf_roh`
            # antwortet dann selbst (fail closed: objekt_unbekannt).
            merker.setdefault(("objekt", typ, name), None)
            continue
        eintrag = _Zeile(objekte[name])
        merker.setdefault(("objekt", typ, name), eintrag)
        schluessel = ("objekt_kontext", typ, name, benutzer)
        if schluessel in merker:
            continue
        # EINE Sitzung fuer die ganze Schleife: `_stufen_kontext` liest nur
        # (Objekt ist schon da), ein Schreibvorgang dazwischen kann es nicht geben.
        with lesesitzung() as sess:
            merker[schluessel] = (eintrag, kern._stufen_kontext(sess, benutzer, typ, eintrag))

        for aktion in (kern.LESEN, kern.SCHREIBEN, kern.VORSCHLAGEN,
                       kern.MODERIEREN, kern.VERWALTEN):
            s = ("darf", benutzer, aktion, typ, name, None, None, None, (), kern.STUFE_GEMEINDE)
            if s not in merker:
                merker[s] = kern._darf_roh(benutzer, aktion, typ, name)
        for s, roh in (
            (("pruefstufen", benutzer, typ, name), kern._pruefstufen_roh),
            (("moderationsstufen", benutzer, typ, name), kern._moderationsstufen_roh),
        ):
            if s not in merker:
                merker[s] = roh(benutzer, typ, name)
